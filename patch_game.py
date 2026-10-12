import os
import shutil
import struct
import sys

EXE_PATH = "WAL.exe"
BAK_PATH = EXE_PATH + ".bak"

def generate_travel_to_map_payload():
    """
    Directly calls UWALGameManager::TravelToMap(wchar_t* URL, UWorld* World)
    bypassing the ProcessEvent RPC layer completely.
    100% Position-Independent Code (PIC) with ?listen parameter for hosting!
    Checks bHasSelectedGameMode ([rcx + 0x851] != 0) so it ONLY fires inside the pod!
    """
    START_RVA = 0x2891B0
    GET_GM_RVA = 0x251890
    TRAVEL_TO_MAP_RVA = 0x245FE0

    TDM_STR = "/Game/Maps/TDM/TDM_Balltuga/TDM_Balltuga?listen\0".encode("utf-16le")
    GR_STR  = "/Game/Maps/GR/GR_SkullTemple/GR_SkullTemple?listen\0".encode("utf-16le")

    code = bytearray()

    # 0. Check [rcx + 0x851] (bHasSelectedGameMode)
    # If 0 (player not in pod), return immediately!
    code.extend(bytes.fromhex("80 b9 51 08 00 00 00"))   # cmp byte ptr [rcx + 0x851], 0
    je_ret1_idx = len(code)
    code.extend(bytes.fromhex("74 00"))                  # je do_early_ret (placeholder)

    # Check [rcx + 0xbb8] (m_bTravelling)
    # If 1 (already travelling), return immediately!
    code.extend(bytes.fromhex("80 b9 b8 0b 00 00 00"))   # cmp byte ptr [rcx + 0xbb8], 0
    jne_ret2_idx = len(code)
    code.extend(bytes.fromhex("75 00"))                  # jne do_early_ret (placeholder)

    # Prologue:
    code.extend(bytes.fromhex("53"))                     # push rbx
    code.extend(bytes.fromhex("41 54"))                  # push r12
    code.extend(bytes.fromhex("41 57"))                  # push r15
    code.extend(bytes.fromhex("48 83 ec 20"))            # sub rsp, 0x20 (shadow space, 16-byte aligned)

    code.extend(bytes.fromhex("48 89 cb"))               # mov rbx, rcx (PlayerController)
    code.extend(bytes.fromhex("c6 83 b8 0b 00 00 01"))   # mov byte ptr [rbx + 0xbb8], 1 (m_bTravelling = 1)

    # 1. Get UWorld* from PlayerController->GetWorld()
    code.extend(bytes.fromhex("48 8b 03"))               # mov rax, qword ptr [rbx]
    code.extend(bytes.fromhex("48 89 d9"))               # mov rcx, rbx
    code.extend(bytes.fromhex("ff 90 08 01 00 00"))      # call qword ptr [rax + 0x108]
    code.extend(bytes.fromhex("49 89 c4"))               # mov r12, rax (r12 = UWorld*)

    # 2. Get UWALGameManager*
    call_get_gm_rel = GET_GM_RVA - (START_RVA + len(code) + 5)
    code.extend(bytes.fromhex("e8"))                     # call GetGameManager
    code.extend(struct.pack("<i", call_get_gm_rel))
    code.extend(bytes.fromhex("49 89 c7"))               # mov r15, rax (r15 = UWALGameManager*)

    # 3. Select Map URL based on [rbx + 0x850]
    code.extend(bytes.fromhex("80 bb 50 08 00 00 00"))   # cmp byte ptr [rbx + 0x850], 0

    str_tdm_offset = 0x80
    str_gr_offset  = 0xE0

    # je is_gr (+9 bytes -> skip lea tdm and jmp)
    code.extend(bytes.fromhex("74 09"))                  # je +9

    # lea rdx, [rip + disp_tdm]
    disp_tdm = str_tdm_offset - (len(code) + 7)
    code.extend(bytes.fromhex("48 8d 15"))               # lea rdx, [rip + disp_tdm]
    code.extend(struct.pack("<i", disp_tdm))

    # jmp do_travel (+7 bytes -> skip lea gr)
    code.extend(bytes.fromhex("eb 07"))                  # jmp +7

    # is_gr:
    disp_gr = str_gr_offset - (len(code) + 7)
    code.extend(bytes.fromhex("48 8d 15"))               # lea rdx, [rip + disp_gr]
    code.extend(struct.pack("<i", disp_gr))

    # do_travel:
    code.extend(bytes.fromhex("4c 89 f9"))               # mov rcx, r15 (rcx = UWALGameManager*)
    code.extend(bytes.fromhex("4d 89 e0"))               # mov r8, r12 (r8 = UWorld*)

    # 4. Call UWALGameManager::TravelToMap(wchar_t* URL, UWorld* World)
    call_travel_rel = TRAVEL_TO_MAP_RVA - (START_RVA + len(code) + 5)
    code.extend(bytes.fromhex("e8"))                     # call TravelToMap
    code.extend(struct.pack("<i", call_travel_rel))

    # epilogue:
    code.extend(bytes.fromhex("48 83 c4 20"))            # add rsp, 0x20
    code.extend(bytes.fromhex("41 5f"))                  # pop r15
    code.extend(bytes.fromhex("41 5c"))                  # pop r12
    code.extend(bytes.fromhex("5b"))                     # pop rbx
    code.extend(bytes.fromhex("c3"))                     # ret

    # do_early_ret:
    early_ret_offset = len(code)
    code.extend(bytes.fromhex("c3"))                     # ret

    # Patch early return jumps
    code[je_ret1_idx + 1]  = early_ret_offset - (je_ret1_idx + 2)
    code[jne_ret2_idx + 1] = early_ret_offset - (jne_ret2_idx + 2)

    # Pad code to 0x80
    assert len(code) <= str_tdm_offset, f"Code too large: {len(code)} > {str_tdm_offset}"
    code.extend(b"\x90" * (str_tdm_offset - len(code)))

    # Offset 0x80: TDM_STR
    code.extend(TDM_STR)

    # Pad to 0xE0
    assert len(code) <= str_gr_offset, f"TDM string too large: {len(code)} > {str_gr_offset}"
    code.extend(b"\x00" * (str_gr_offset - len(code)))

    # Offset 0xE0: GR_STR
    code.extend(GR_STR)

    rem = len(code) % 16
    if rem != 0:
        code.extend(b"\x00" * (16 - rem))

    return bytes(code)

TRAVEL_TO_MAP_PAYLOAD = generate_travel_to_map_payload()

# jmp from StartTravelling (RVA 0x289840) to StartSquadTravelling (RVA 0x2891B0)
# rel32 = 0x2891B0 - (0x289840 + 5) = -0x695
JMP_START_SQUAD = b"\xe9" + struct.pack("<i", -0x695)

PATCHES = [
    {
        "name": "PE DllCharacteristics DYNAMIC_BASE / ASLR disable",
        "offset": 0x1EE,
        "original": bytes.fromhex("60 81"),
        "patched":  bytes.fromhex("20 81")
    },
    {
        "name": "CheckServerStatus bypass",
        "offset": 0x21DA70,
        "original": bytes.fromhex("48 89 5c 24 08"),
        "patched":  bytes.fromhex("c3 90 90 90 90") # ret, nop, nop, nop, nop
    },
    {
        "name": "GetTDMAvailable unlock",
        "offset": 0x1A19F0,
        "original": bytes.fromhex("48 83 ec 28 e8"),
        "patched":  bytes.fromhex("b0 01 c3 90 90") # mov al, 1; ret; nop; nop
    },
    {
        "name": "GetGRAvailable unlock",
        "offset": 0x19D360,
        "original": bytes.fromhex("48 83 ec 28 e8"),
        "patched":  bytes.fromhex("b0 01 c3 90 90") # mov al, 1; ret; nop; nop
    },
    {
        "name": "GetGameModeDisplayInstructions bypass (removes 'not available' text)",
        "offset": 0x2299FC,
        "original": bytes.fromhex("45 84 c0 75 2c 44 38 41 60 75 58"),
        "patched":  bytes.fromhex("eb 61 90 90 90 90 90 90 90 90 90") # jmp short to available
    },
    {
        "name": "CreateSquad DailyFreeGames check bypass",
        "offset": 0x2697BE,
        "original": bytes.fromhex("0f 8e 65 01 00 00"),
        "patched":  bytes.fromhex("90 90 90 90 90 90") # nop
    },
    {
        "name": "CreateSquad EnableMatchMaking check bypass",
        "offset": 0x2697C8,
        "original": bytes.fromhex("0f 84 5b 01 00 00"),
        "patched":  bytes.fromhex("90 90 90 90 90 90") # nop
    },
    {
        "name": "CreateSoloGame 0x3a check bypass",
        "offset": 0x269157,
        "original": bytes.fromhex("75 58"),
        "patched":  bytes.fromhex("eb 58") # jmp short to success
    },
    {
        "name": "GameManager ctor bTDMAvailable unlock",
        "offset": 0x2BD348,
        "original": bytes.fromhex("c7 43 5c 00 00 00 00"),
        "patched":  bytes.fromhex("c7 43 5c 00 00 00 01") # sets bTDMAvailable (0x5f) = 1
    },
    {
        "name": "GameManager ctor bGRAvailable unlock",
        "offset": 0x2BD360,
        "original": bytes.fromhex("66 c7 43 60 00 00"),
        "patched":  bytes.fromhex("66 c7 43 60 01 00") # sets bGRAvailable (0x60) = 1
    },
    {
        "name": "GetTitleAndDescription GR lock bypass",
        "offset": 0x1D784B,
        "original": bytes.fromhex("0f 84 c9 00 00 00"),
        "patched":  bytes.fromhex("90 90 90 90 90 90") # nop (never jump to GRBoxLocked)
    },
    {
        "name": "GetTitleAndDescription TDM lock bypass",
        "offset": 0x1D7962,
        "original": bytes.fromhex("0f 84 c9 00 00 00"),
        "patched":  bytes.fromhex("90 90 90 90 90 90") # nop (never jump to TDMBoxLocked)
    },
    {
        "name": "WALMatchMakingInterface IsValid unlock",
        "offset": 0x1A8200,
        "original": bytes.fromhex("48 83 ec 28"),
        "patched":  bytes.fromhex("b0 01 c3 90") # mov al, 1; ret; nop
    },
    {
        "name": "WALRankingInterface IsValid unlock",
        "offset": 0x1A8240,
        "original": bytes.fromhex("48 83 39 00 74 09 80 79 08 00 74 03 b0 01 c3 32 c0 c3"),
        "patched":  bytes.fromhex("b0 01 c3 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90") # mov al, 1; ret; nops
    },
    {
        "name": "GetClassRanking unlock",
        "offset": 0x19B6F0,
        "original": bytes.fromhex("40 53 48 83 ec 20"),
        "patched":  bytes.fromhex("b8 01 00 00 00 c3") # mov eax, 1; ret
    },
    {
        "name": "NotifyActorBeginOverlap m_bIsOpen unblock",
        "offset": 0x2AFB76,
        "original": bytes.fromhex("0f 84 01 01 00 00"),
        "patched":  bytes.fromhex("90 90 90 90 90 90") # nop
    },
    {
        "name": "IsFreeUser unlock (always return 0 / Paid User)",
        "offset": 0x2348E0,
        "original": bytes.fromhex("40 53 48 83 ec 20"),
        "patched":  bytes.fromhex("31 c0 c3 90 90 90") # xor eax, eax; ret; nops
    },
    {
        "name": "TravelToMap online session check bypass (jump direct to UWorld::ServerTravel)",
        "offset": 0x2454FE,
        "original": bytes.fromhex("0f 84 9e 02 00 00"),
        "patched":  bytes.fromhex("e9 9f 02 00 00 90") # jmp to 0x1402463a2, nop
    },
    {
        "name": "StartSquadTravelling direct TravelToMap hook",
        "offset": 0x2885B0,
        "original": None, # Will be read from BAK
        "patched":  TRAVEL_TO_MAP_PAYLOAD
    },
    {
        "name": "StartTravelling entry redirect to StartSquadTravelling",
        "offset": 0x288C40,
        "original": bytes.fromhex("40 55 57 48 8d"),
        "patched":  JMP_START_SQUAD
    }
]

def backup():
    if not os.path.exists(BAK_PATH):
        print(f"[+] Creating backup: {BAK_PATH}")
        shutil.copy2(EXE_PATH, BAK_PATH)
        print("[+] Backup created successfully!")
    else:
        print(f"[*] Backup already exists: {BAK_PATH}")

def patch():
    if not os.path.exists(EXE_PATH):
        print(f"[-] Game executable not found at: {EXE_PATH}")
        return False
    
    backup()
    
    # Read original bytes from BAK for dynamic payload length
    with open(BAK_PATH, "rb") as f_bak:
        for p in PATCHES:
            if p["original"] is None:
                f_bak.seek(p["offset"])
                p["original"] = f_bak.read(len(p["patched"]))
    
    # Fresh restore from BAK before patching to guarantee clean state
    print("[*] Restoring clean base from WAL.exe.bak before applying patches...")
    shutil.copy2(BAK_PATH, EXE_PATH)
    
    all_ok = True
    with open(EXE_PATH, "r+b") as f:
        for p in PATCHES:
            f.seek(p["offset"])
            current = f.read(len(p["original"]))
            if current == p["patched"]:
                print(f"[*] {p['name']} is already applied.")
            elif current == p["original"]:
                f.seek(p["offset"])
                f.write(p["patched"])
                print(f"[+] {p['name']} applied successfully at 0x{p['offset']:X} ({len(p['patched'])} bytes)!")
            else:
                print(f"[-] Unexpected bytes at 0x{p['offset']:X} ({p['name']}): {current.hex(' ')[:30]}...")
                all_ok = False
                
    if all_ok:
        print(f"\n[SUCCESS] All {len(PATCHES)} patches applied cleanly!")
    else:
        print("\n[WARNING] Some patches had unexpected bytes.")
    return all_ok

def restore():
    if not os.path.exists(BAK_PATH):
        print(f"[-] Backup file not found: {BAK_PATH}")
        return False
    shutil.copy2(BAK_PATH, EXE_PATH)
    print(f"[+] Restored original WAL.exe from backup!")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--restore":
        restore()
    else:
        patch()
