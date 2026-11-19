# GRG-4361u WAN Setting Tool V1.0.5 — 10-unit Pilot

Windows 11 / Edge, compile using GitHub Actions on Python 3.11. Pilot: only use on recoverable test DUTs until station acceptance is signed.

## WAN target
nas0_0, VLAN ID=160, multicast VLAN ID=160, priority 0 (HTTP value 1), INTERNET/IPoE, bridge enabled / transparent, NAPT disabled, MTU 1500, fixed IPv4 192.168.2.121–192.168.2.130 (operator-selected), gateway 192.168.2.100, subnet 255.255.255.0, request DNS disabled, LAN_1 10GE mapping enabled.

## Per-device workflow (repeat up to 10 times)
1. Attach ONE DUT via LAN (default DUT management IP 192.168.1.1). Restore DUT to expected baseline if necessary. Select free target static IP from the dropdown.
2. Scan MAC and GPON SN labels (or type them). GPON SN must equal `CMTD` + final eight hex digits of scanned MAC. Enter operator.
3. Click `Read & Compare`; 19 fields are compared against the selected target IP using the DUT `links[]` values extracted from `/admin/multi_wan_generic.asp`. This does **not** prove the scanned label belongs to the connected DUT: independently verify label/device mapping.
4. On a test DUT, click `EXPERIMENTAL Apply & Verify` and confirm. This reserves selected IP in a durable CSV ledger **before** submitting a POST. A reserved or confirmed IP for another MAC is rejected.
5. A successful readback of 19/19 settings produces `OK`; a mismatch produces NG; missing data produces `VERIFY_INCOMPLETE`. Compare actual Web GUI after pilot test. After OK the UI clears identifiers and selects the next free IP.
6. The allocation CSV/XLSX and cumulative Master Record are created under `records/` next to the working directory. Preserve the ENTIRE `records/` folder between devices and executions.

## Excel / history
`records/WAN_IP_Allocation.xlsx` has timestamp, event, result, operator, MAC, GPON SN, target IP, DUT management IP, and notes. `WAN_IP_Allocation.csv` is the transaction authority; each reservation and attempt appends a row. `WAN_Master_Record.xlsx` retains detailed before/after comparison. Do **not** delete either CSV when switching devices. To share allocations among multiple PCs, use a **single shared record database**; this pilot only protects IPs within the same records folder and cannot detect independent workstations or other non-tool assignments.

`RESERVED` and `HOLD` also block allocation; a write with uncertain result is HOLD, not automatically released. Reassignment must be reviewed manually using both DUT Web GUI and records. Do not edit the CSV while the application runs. If the ledger XLSX is open in Excel and cannot be updated, close Excel and resume the tool; CSV continues to be authoritative.

## Engineering safety
- Same target IP in different DUTs is blocked **only** when the same persistent `records/` folder is used; DUT identity comes from **operator scans**, not authenticated device-read identifiers. MAC/GPON format relationship is checked, but actual DUT ownership is not yet read and cross-verified.
- WAN configuration can interrupt TR069/internet. No verified rollback. No mass unattended writes. Never run simultaneously on two PCs against distinct copies of allocation CSV.
- The readback confirms configured values represented by device Web GUI initialization data, not actual end-to-end IP/optical connectivity or persistent storage across a power cycle.
- LAN management 192.168.1.1 is distinct from static WAN IP range 192.168.2.121–130.

## Build
Upload only Clean ZIP contents to a new GitHub repository root; Actions > GRG4361 WAN Windows Build > Run workflow. Do not upload `records/` and do not embed real credentials.
