"""Explicit fictional 14-slot scenario. Only new, isolated test-output DBs."""
import argparse
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from .config import ROOT, Settings
from .database import Database
from .documents import stamp, uid
from .migrations import migrate
from .s02_service import seed_demo
from .web import create_app

PATIENT='demo-patient-a-self'
SCENARIO='s03-fixed-14-v1'
ZONE=ZoneInfo('Asia/Shanghai')
ORIGIN='http://127.0.0.1:8000'


def generate(path, *, add_late_report=False):
    path=Path(path).resolve()
    if not path.is_relative_to((ROOT/'test-output').resolve()):
        raise ValueError('Scenario database must be explicitly isolated under test-output')
    manifest_path=path.with_suffix('.scenario.json')
    current=datetime.now(timezone.utc)
    if add_late_report:
        if not path.is_file() or not manifest_path.is_file():
            raise ValueError('Existing scenario manifest required')
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['scenario']!=SCENARIO:
            raise ValueError('Unrecognized scenario')
        clock=[current]
    else:
        if path.exists() or manifest_path.exists():
            raise ValueError('Refusing to overwrite an existing database or scenario')
        path.parent.mkdir(parents=True,exist_ok=True)
        first=current.astimezone(ZONE).date()-timedelta(days=7)
        clock=[datetime.combine(first,time(),ZONE).astimezone(timezone.utc)]
        db=Database(path);migrate(db,initialize=True);seed_demo(db,lambda:clock[0])
    app=create_app(Settings(_env_file=None,APP_ENV='test',DATABASE_PATH=path),clock=lambda:clock[0])
    clients=[]
    def login(account):
        client=TestClient(app,base_url=ORIGIN);clients.append(client)
        r=client.post('/api/v1/auth/demo-session',json={'demo_account_id':account},headers={'Origin':ORIGIN,'Idempotency-Key':uid()})
        if r.status_code!=201:
            raise RuntimeError('Scenario login failed')
        client.csrf=r.json()['data']['csrf_token'];return client
    def call(client,method,path,body=None):
        r=client.request(method,'/api/v1'+path,json=body,headers={'Origin':ORIGIN,'X-CSRF-Token':client.csrf,'Idempotency-Key':uid()})
        if r.status_code>=300:
            raise RuntimeError('Scenario API failed: '+r.json()['error']['code'])
        return r.json()['data']
    try:
        a=login('demo-patient-a')
        if not add_late_report:
            med=call(a,'POST',f'/patients/{PATIENT}/medications',{'name':'虚构演示药品（不用于实际服药）'})
            entry={'draft_entry_id':uid(),'medication_id':med['medication_id'],'dose_value':'1','dose_unit':'虚构单位',
                   'start_date':str(first),'end_date':None,'schedule':{'kind':'daily','times':['08:00','20:00'],'weekdays':[]},
                   'meal_requirement':None,'medical_notes':'虚构场景，不提供医嘱','strict_timing':False,'min_interval_minutes':None,'source_file_ids':[]}
            draft=call(a,'POST',f'/patients/{PATIENT}/drafts',{'entries':[entry],'source_file_ids':[]})
            draft=call(a,'POST',f"/drafts/{draft['draft_id']}/submit",{'expected_revision':draft['meta']['revision'],'content_revision':draft['content_revision']})
            call(a,'POST',f'/patients/{PATIENT}/plan-confirmations',{'draft_id':draft['draft_id'],'draft_revision':draft['content_revision'],
                'existing_plan_id':None,'expected_plan_version':None,'effective_from':stamp(clock[0]),'confirmed':True})
            prefs={'enabled':True,'channels':['in_app'],'sound_enabled':False,'vibration_enabled':False,'routine_mode':'regular',
                   'anchors':[],'privacy_enabled':True,'custom_text':None,'privacy_windows':[],'repeat_interval_minutes':None,
                   'max_repeats':0,'snooze_minutes':10,'notify_family':False}
            call(a,'PUT',f'/patients/{PATIENT}/reminder-preferences',{'expected_revision':0,'settings':prefs})
            start=stamp(datetime.combine(first,time(),ZONE));end=stamp(datetime.combine(first+timedelta(days=7),time(),ZONE))
            app.state.s03_execution.maintenance(None,PATIENT,start,stamp(datetime.combine(first+timedelta(days=1),time(),ZONE)))
            with app.state.db.connection(readonly=True) as c:
                tasks=[json.loads(row[0]) for row in c.execute('SELECT document_json FROM a_tasks')]
            task=min(tasks,key=lambda t:t['scheduled_at'])
            clock[0]=datetime.fromisoformat(task['scheduled_at'])
            executed=app.state.s03_execution.run_once(None,task['task_id'],task['meta']['revision'],SCENARIO+'-notification').data
            clock[0]=current;a=login('demo-patient-a');admin=login('demo-admin')
            with app.state.db.connection(readonly=True) as c:
                slots=[dict(r) for r in c.execute('SELECT * FROM dose_slots WHERE patient_id=? AND scheduled_at>=? AND scheduled_at<? ORDER BY scheduled_at',(PATIENT,start,end))]
            if len(slots)!=14:
                raise RuntimeError('Scenario did not materialize 14 doses')
            def report(index):
                slot=slots[index]
                return call(a,'POST',f'/patients/{PATIENT}/medication-events',{'source_event_id':SCENARIO+'-self-'+str(index),
                    'occurred_at':slot['scheduled_at'],'reported_status':'taken','dose_slot_id':slot['dose_slot_id'],
                    'medication_id':slot['medication_id'],'plan_ref':{'plan_id':slot['plan_id'],'plan_version':slot['plan_version']}})
            for index in range(10): report(index)
            call(a,'POST',f'/patients/{PATIENT}/device-bindings',{'device_id':'demo-box-a','confirmed':True})
            for index in (10,11):
                body={'patient_id':PATIENT,'device_id':'demo-box-a','scenario':'normal_box','scenario_run_id':SCENARIO+'-box-'+str(index),'occurred_at':slots[index]['scheduled_at']}
                event=call(admin,'POST','/demo/device-events',body)
                call(admin,'POST','/demo/device-events',body)  # A stable repeated source produces one fact.
                call(admin,'POST','/dose-matches/review',{'event_id':event['event_id'],'expected_revision':1,'dose_slot_id':slots[index]['dose_slot_id'],
                    'reason':'固定虚构场景明确核对单药时段，不按附近时间猜测'})
            for suffix,payload in [('zero',{'metric_code':'step_count','value':0,'unit':'count','method_code':'manual_entry','missing_reason':None}),
                ('missing',{'metric_code':'sleep_duration','value':None,'unit':'h','method_code':None,'missing_reason':'虚构场景未采集'}),
                ('unknown-unit',{'metric_code':'heart_rate','value':70,'unit':'demo_unknown','method_code':None,'missing_reason':None})]:
                call(a,'POST',f'/patients/{PATIENT}/measurements',{'source_event_id':SCENARIO+'-'+suffix,'occurred_at':slots[-1]['scheduled_at'],'payload':payload})
            manifest={'scenario':SCENARIO,'is_simulated':True,'clock_mode':'explicit isolated fixture; final clock is actual UTC',
                      'window_start':start,'window_end':end,'late_slot':slots[12],
                      'mock_execution_id':executed['execution_id'],'delivery_status':executed['delivery_status']}
        else:
            slot=manifest['late_slot']
            call(a,'POST',f'/patients/{PATIENT}/medication-events',{'source_event_id':SCENARIO+'-self-12',
                'occurred_at':slot['scheduled_at'],'reported_status':'taken','dose_slot_id':slot['dose_slot_id'],
                'medication_id':slot['medication_id'],'plan_ref':{'plan_id':slot['plan_id'],'plan_version':slot['plan_version']}})
        window={k:manifest[k] for k in ('window_start','window_end')}
        app.state.s03_execution.maintain_due(None,PATIENT)
        summary=call(a,'POST',f'/patients/{PATIENT}/summary-refresh',{**window,'data_environment':'demo'})
        stats=summary['record_overview']
        manifest.update(summary_id=summary['summary_id'],statistics_id=stats['statistics_id'],as_of=stats['as_of'],
                        planned_dose_count=stats['planned_dose_count'],patient_confirmed_count=stats['patient_confirmed_count'],
                        patient_confirmation_ratio=stats['patient_confirmation_ratio'])
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
        return manifest
    finally:
        for client in clients: client.close()


def main():
    parser=argparse.ArgumentParser(description='Explicit fictional S03 scenario; never overwrites an existing database')
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--add-late-report',action='store_true')
    args=parser.parse_args()
    try:
        result=generate(args.database,add_late_report=args.add_late_report)
        print(json.dumps({k:result[k] for k in ('scenario','window_start','window_end','as_of','planned_dose_count','patient_confirmed_count','patient_confirmation_ratio','delivery_status')},ensure_ascii=False))
        return 0
    except (ValueError,RuntimeError):
        print('演示生成失败：目标必须是明确隔离的新库；核对已有场景、schema与运行说明。')
        return 2


if __name__=='__main__':
    raise SystemExit(main())
