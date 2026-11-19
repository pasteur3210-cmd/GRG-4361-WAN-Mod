from wan_tool import comparison_summary, save_manual_review
import json

def test_summary_unknown():
    assert comparison_summary({'a':{'status':'MATCH'},'b':{'status':'UNKNOWN'}})[0]=='VERIFY_INCOMPLETE'

def test_summary_diff():
    assert comparison_summary({'a':{'status':'DIFF'},'b':{'status':'UNKNOWN'}})[0]=='NG'

def test_summary_all_ok():
    assert comparison_summary({'a':{'status':'MATCH'}})[0]=='OK'

def test_manual_review_keeps_unknown(tmp_path):
    comparison={'ip':{'status':'UNKNOWN'},'vid':{'status':'MATCH'}}
    record=save_manual_review(tmp_path,'192.168.1.1',comparison,True,'QA','Screenshots checked')
    assert record['manual_result']=='MANUAL_OK'
    assert record['automatic_result']=='VERIFY_INCOMPLETE'
    assert comparison['ip']['status']=='UNKNOWN'
    assert json.loads((tmp_path/'manual_reviews.jsonl').read_text())['operator']=='QA'
