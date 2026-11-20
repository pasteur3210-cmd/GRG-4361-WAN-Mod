# GRG-4361u WAN Setting Tool V1.1.2

Production-oriented release candidate based on verified V1.0.9 WAN post/readback.

## Operating procedure

1. Compile on GitHub Actions Windows runner (Python 3.11). Keep the existing `records` folder beside the EXE.
2. Launch the tool; use **Change Operator** once before scanning devices. Operator stays locked for scanner operation.
3. Scan MAC then GPON SN. Scanner Enter moves MAC -> GPON; Enter in GPON does not move to Operator or trigger Apply.
4. Select target WAN IP from 192.168.2.121–130; perform Read & Compare, then confirm Apply only for intended DUT.
5. Confirm 19/19 target matches, all cross-WAN changes permitted and Excel results appended under `records/GRG4361_WAN_Master_Record.xlsx`.
6. After a successful Apply, only MAC and GPON SN clear and focus returns to MAC. Operator and connection credentials stay unchanged.

## Release limitations

GUI scanner sequence and packaging verified by automated tests on available platform; actual Windows EXE build and V1.1.2 multi-device operating validation must be confirmed on target Windows environment. Do not claim operational qualification until verified. Production use requires reviewing IP assignments for all production test PCs; per-folder records alone are not a distributed IP allocator.


## V1.1.2 Restore Default Verification
- Restore Default is **manual**; this tool only reads WAN settings.
- First restore and independently check a reference DUT, then use `Capture Factory Golden (once)` to store its three WAN configurations under `records/GRG4361_Factory_Default_Golden.json` with SHA256. Review the Golden before production use. Never capture an unverified DUT or a modified test state.
- For each DUT, manually Restore Default and allow reboot. Scan MAC and GPON SN, press `4. Verify Default Settings`. The comparison is read-only and checks every captured field on nas0_0, nas0_1, nas0_2. Missing values are UNKNOWN, differing values FAIL, matching values PASS.
- Summary, per-field differences and Test History are appended to the same Excel workbook (`records/GRG4361_WAN_Master_Record.xlsx`), on two additional tabs. Three-sheet V1.1.0 records are upgraded without deleting existing rows.
- No official default values have been independently provided; Golden capture requires operator confirmation and is not a factory-signed reference. Production approval requires actual restored reference verification.
- WARNING: open Excel workbooks may prevent concurrent writes; close Excel before running a test.
