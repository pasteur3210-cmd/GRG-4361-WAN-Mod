# GRG-4361u WAN Setting Tool V1.1.4

## V1.1.4: New Batch / Reset IP Allocation

The GUI has a new **New Batch / Reset IP Allocation** button. Enter a unique, short Batch ID (e.g. `MP20261123_001`) and confirm that the previous batch's testing/Default Verification is complete and its DUTs are reset or disconnected from the test network. Creating a new batch **does not delete or edit previous-batch records**. It creates a fresh independent IP Allocation and WAN Master Record for use of `192.168.2.121` through `.130` again.

**Important physical safety constraint:** different batches can reuse the same static addresses only after the previous batch's devices have been removed from the shared test LAN or restored so they no longer hold those addresses. This tool cannot detect other live devices on the network, and it is **not** a multi-PC centralized allocator. Production mode still blocks conflicting MACs **within the current batch**.

### Storage layout and version migration

```
EXE folder/
  GRG4361_WAN_Setting_V1.1.4.exe
  records/
    active_batch.json                          # created upon first New Batch
    GRG4361_WAN_Master_Record.xlsx            # legacy V1.1.3 records, never deleted
    GRG4361_Factory_Default_Golden.json       # preserved legacy Golden
    before.json, after.json, execution.log... # preserved legacy logs
    batches/
      MP20261123_001/
        batch_info.json
        GRG4361_WAN_Master_Record.xlsx        # independent batch/IP allocations
        GRG4361_Factory_Default_Golden.json   # validated copy from prior batch
        execution.log, before.json, ...       # this batch's logs
      MP20261123_002/
        batch_info.json
        GRG4361_WAN_Master_Record.xlsx
        GRG4361_Factory_Default_Golden.json
        ...
```

Before the first **New Batch**, V1.1.4 uses the existing `records` directory and identifies it as **LEGACY**, preserving previous behavior. After creation it saves the active Batch ID in `records/active_batch.json`; closing/restarting EXE resumes the same batch. Every batch has its own XLSX and per-DUT log files, and the previous batch is still stored at its original path. Batch IDs cannot be reused (to prevent accidental mixing of historical records). **Never delete `active_batch.json` to reset IPs**: use the GUI. If a referenced batch folder is missing, startup deliberately fails instead of silently restarting allocations.

The Golden Default is copied from the previous active batch into the new batch, preserving the site Golden without recapturing it. If the previous batch has no Golden yet, the bundled user-supplied reference is installed; this reference is not an independently certified factory baseline. It requires QA approval against an actual restored reference DUT before formal use.

### Recommended operating sequence

1. Start or resume the batch. Enter operator once and scan MAC and GPON SN for each DUT.
2. Run **Read & Compare**, then **Apply & Verify**. Validate 19/19 required matches and acceptable 10GE transfer.
3. Close the tool if necessary; perform product testing and manual Restore Default separately.
4. Reopen the tool (same EXE folder and batch), scan the **same** MAC and GPON SN and press **Verify Default Settings**. This read-only step can run without Read/Apply in that session. Excel links persisted records **only within the current batch**.
5. After completing ALL DUTs' WAN Setting and Default Verification, disconnect/restore old DUTs; then click **New Batch / Reset IP Allocation** to release the ten addresses for the new batch. Do not switch early if Default Verification must link to the previous batch's WAN Apply.

### Existing functions retained

- Operator locked outside the MAC / GPON SN scanner focus sequence; after a successful Apply the scanner focus returns to MAC.
- `nas0_0` WAN target: VLAN 160, multicast VLAN 160, IPoE, static IP `.121–.130`, gateway `.100`, mask `255.255.255.0`, 10GE mapping. HTTP POST behavior retained from V1.1.3.
- READ displays READY_TO_APPLY or ALREADY_CONFIGURED rather than falsely marking a normal before-state as final NG.
- Single append-only XLSX per batch: WAN Setting Master Record, IP Allocation, Test History, Default Verification Summary and Detail.
- Default verification reads three WAN interfaces (57 Golden field comparisons) and never triggers Restore Default on the device.

### Release restrictions

Local source tests ran on Python 3.13 (50/50 PASS). Python 3.11 and Windows GitHub Actions are configured in `.github/workflows/build.yml` but were not executed in this environment. The new GUI button, Windows EXE operation and actual DUT IP reuse require target-site acceptance. Do not treat an automatically passed Python test as a production validation of the new workflow.

Close the workbook in Microsoft Excel before the program writes. Keep only one instance of the tool per test station. Back up `records` across software upgrades.
