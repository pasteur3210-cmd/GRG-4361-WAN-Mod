# GRG-4361u WAN Setting Tool V1.0.8 (Pilot)

## Main changes
- A single cumulative `records/GRG4361_WAN_Master_Record.xlsx` alongside the executable.
- Three worksheets: WAN Setting Master Record, IP Allocation, Test History.
- CSV files are **not generated** by normal V1.0.8 operation.
- Engineering / Production modes; the same MAC + IP may be retested, different MAC + IP is rejected even in Engineering mode.
- Production mode also rejects moving an already-allocated MAC to a different IP.
- Optional one-time legacy CSV import; no mandatory import in Engineering mode.
- OK/Cancel Apply confirmation; before applying show READY_TO_APPLY, not NG.
- Continue preserving known-good V1.0.6 WAN POST/19-field readback and selective nas0_2 → nas0_0 10GE transfer.

## Usage
1. Build with GitHub Actions on Python 3.11 / Windows runner.
2. Extract/run EXE from a **writable folder** (not Program Files or a protected network directory).
3. `records/GRG4361_WAN_Master_Record.xlsx` appears automatically. Do not keep it open in Excel when writing.
4. If previous production IP records exist, import `WAN_IP_Allocation.csv` before allocating any new production devices. Import separately for each old records folder.
5. Engineering: repeat the same two DUT identities and IPs with new history rows. Production: assign 192.168.2.121-130 uniquely.
6. Read & Compare, then Apply (test DUT only), then inspect overall result and Excel.

## Storage and migration safeguards
- The workbook is the persistent source of truth **for this folder**. Switching EXE folder makes a new ledger; move/copy the entire `records` folder when replacing a build, or choose a fixed EXE location.
- A new workbook cannot detect previous allocations on other computers. For Production, import audited legacy records, or run from a shared controlled workspace with serialized operation.
- The original V1.0.7 AppData ledger is not deleted or silently migrated. Backup it and import its CSV if necessary.
- Legacy CSVs may still be created by *legacy unit tests* in temporary test directories; the V1.0.8 GUI does not create CSV reports.
- Current release is Pilot; Windows GitHub Actions and DUT validation are pending.
