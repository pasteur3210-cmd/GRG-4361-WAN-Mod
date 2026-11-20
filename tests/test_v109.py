from pathlib import Path
import tempfile
from unified_store import ensure_workbook, add_history, read_rows, workbook_path
from wan_tool import WanSession, comparison_summary


def test_master_final_only_and_history_complete():
    with tempfile.TemporaryDirectory() as td:
        ensure_workbook(td)
        add_history(td, 'V1.0.9', 'Engineering','192.168.1.1','READ','READY_TO_APPLY','001122AABBCC','CMTD22AABBCC','192.168.2.121','QA','12 DIFF')
        add_history(td, 'V1.0.9', 'Engineering','192.168.1.1','APPLY','OK','001122AABBCC','CMTD22AABBCC','192.168.2.121','QA','19 MATCH')
        assert len(read_rows(td,0)) == 1
        assert read_rows(td,0)[0]['Result'] == 'OK'
        assert [r['Result'] for r in read_rows(td,2)] == ['READY_TO_APPLY','OK']
        assert workbook_path(td).is_file()


def test_read_stage_logs_precheck_semantics():
    import inspect
    code = inspect.getsource(WanSession.read)
    assert "'READY_TO_APPLY'" in code
    assert "'ALREADY_CONFIGURED'" in code


def test_xlsx_opens_and_has_compatible_styles():
    import zipfile, xml.etree.ElementTree as ET
    from unified_store import ensure_workbook
    with tempfile.TemporaryDirectory() as td:
        path=ensure_workbook(td)
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            styles=ET.fromstring(z.read('xl/styles.xml'))
            ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            count=len(styles.find('m:cellXfs',ns))
            for i in range(1,4):
                sheet=ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'))
                for cell in sheet.findall('.//m:c',ns):
                    assert int(cell.get('s','0')) < count
