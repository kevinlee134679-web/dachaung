"""Isolated acceptance on actual Windows. Rehearsal never counts as Windows acceptance."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
import uuid

from acceptance_process import WindowsApplication,application_pid,release_idle_wrapper,wait_for_shutdown

ROOT=Path(__file__).resolve().parent.parent


def shell_command(arguments):
    # cmd.exe expands these characters even inside some quoted arguments.
    if any(any(char in str(arg) for char in '&|<>^%!\r\n"') for arg in arguments):
        raise RuntimeError('Extract the package to a path without cmd.exe metacharacters.')
    interpreter=os.environ.get('COMSPEC','cmd.exe')
    if any(char in interpreter for char in '&|<>^%!\r\n"'):
        raise RuntimeError('The command interpreter path is not safe to use')
    # Pass the complete command line as a string. Windows list2cmdline uses CRT
    # backslash escaping, which is not cmd.exe's /C command-string syntax.
    return '"'+interpreter+'" /d /s /c "call ' + ' '.join('"'+str(arg)+'"' for arg in arguments)+'"'


def fingerprints(path):
    with closing(sqlite3.connect(path)) as connection:
        names=[n for (n,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {name:hashlib.sha256(json.dumps(sorted(json.dumps(
            [item.hex() if isinstance(item,bytes) else item for item in row],ensure_ascii=False)
            for row in connection.execute('SELECT * FROM "'+name+'"')),ensure_ascii=False).encode()).hexdigest()
            for name in names if name!='schema_migrations'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rehearsal',action='store_true',help='Linux rehearsal only; cannot produce a Windows pass')
    parser.add_argument('--venv',type=Path,help='Existing test environment for rehearsal only')
    parser.add_argument('--browser-package',type=Path,help='Existing Playwright package search directory')
    parser.add_argument('--browser-executable',type=Path)
    args=parser.parse_args()
    native_windows=os.name=='nt' and sys.platform=='win32' and platform.system()=='Windows'
    if native_windows:
        import ctypes
        try:
            native_windows=not hasattr(ctypes.WinDLL('ntdll'),'wine_get_version')
        except OSError:
            native_windows=False
    if not native_windows and not args.rehearsal:
        print('This check must run on Windows. Linux or Wine results cannot close Windows acceptance.')
        return 2
    if args.venv and not args.rehearsal:
        parser.error('Native acceptance always creates its own fresh virtual environment')
    if sys.version_info[:2]!=(3,14):
        print('Install CPython 3.14; the project was verified with 3.14.10.')
        return 2
    os.chdir(ROOT)
    run_dir=ROOT/'test-output'/'windows-acceptance'/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    run_dir.mkdir(parents=True,exist_ok=False)
    environment=run_dir/'venv' if not args.venv else args.venv.resolve()
    python=environment/('Scripts/python.exe' if native_windows else 'bin/python')
    database=run_dir/'fresh demo'/'demo.sqlite3'
    summary=dict(status='running',acceptance_revision=4,native_windows=native_windows,rehearsal=args.rehearsal,
                 system=platform.system(),system_release=platform.release(),python=platform.python_version(),checks=[])
    process=None
    output_stream=None
    application_handle=None
    log_offset=0
    exit_code=2
    env=dict(os.environ,APP_ENV='test',AUTH_MODE='demo',LLM_MODE='mock',DIALOGUE_PIPELINE='single_pass')
    for key in ('LLM_API_KEY','LLM_BASE_URL','LLM_MODEL','DEMO_SERVICE_RECEIPT_TOKEN','DEMO_FULFILLMENT_RECEIPT_TOKEN'):
        env.pop(key,None)

    def check(name,arguments,*,allow_failure=False,timeout=900):
        arguments=[str(a) for a in arguments]
        actual=shell_command(arguments) if native_windows and arguments[0].lower().endswith('.cmd') else arguments
        result=subprocess.run(actual,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout)
        (run_dir/(name+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
        if result.returncode and not allow_failure:
            raise RuntimeError(name+' failed; inspect its private log, or send only RESULT.json first')
        return result

    def passed(name):
        summary['checks'].append(dict(name=name,status='passed'))
        print('[PASS] '+name,flush=True)

    def launch(arguments):
        nonlocal process,output_stream,application_handle,log_offset
        log_file=run_dir/'server.log'
        log_offset=log_file.stat().st_size if log_file.exists() else 0
        output_stream=(run_dir/'server.log').open('a',encoding='utf8')
        command=shell_command(arguments) if native_windows else [str(a) for a in arguments]
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=output_stream,stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE if native_windows else subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if native_windows else 0)
        for _ in range(150):
            try:
                with urlopen(url+'api/v1/health',timeout=1) as response:
                    health=json.load(response)['data']
                    if health['readiness']=='ready':
                        if native_windows:application_handle=WindowsApplication(application_pid(launch_log()))
                        return health
            except (OSError,URLError):
                pass
            if process.poll() is not None:
                raise RuntimeError('The actual launcher exited before service readiness')
            time.sleep(.1)
        raise RuntimeError('Service startup timed out')

    def launch_log():
        with (run_dir/'server.log').open('rb') as stream:
            stream.seek(log_offset)
            return stream.read().decode('utf8',errors='replace')

    def port_closed():
        with socket.socket() as connection:
            connection.settimeout(.2)
            return connection.connect_ex(('127.0.0.1',port))!=0

    def stop():
        nonlocal process,output_stream,application_handle
        if process is None:return
        owned=process
        try:
            if native_windows and application_handle is None:
                raise RuntimeError('No owned Windows application handle was observed; cannot verify shutdown')
            exited=lambda: application_handle.has_exited() if native_windows else owned.poll() is not None
            if not exited():
                owned.send_signal(signal.CTRL_BREAK_EVENT if native_windows else signal.SIGINT)
            evidence=wait_for_shutdown(lambda:dict(application_exited=exited(),port_closed=port_closed(),
                shutdown_log_complete='Application shutdown complete.' in launch_log()))
            cleanup=release_idle_wrapper(owned,application_verified_stopped=True)
            summary.setdefault('shutdowns',[]).append(dict(evidence,wrapper_cleanup=cleanup,
                application_pid=application_handle.pid if native_windows else owned.pid))
        except (OSError,RuntimeError,subprocess.SubprocessError) as error:
            summary['shutdown_diagnostic']=dict(wrapper_pid=owned.pid,
                application_pid=application_handle.pid if application_handle else None,
                port_closed=port_closed(),shutdown_log_complete='Application shutdown complete.' in launch_log())
            if owned.poll() is None:
                if native_windows:
                    subprocess.run(['taskkill','/PID',str(owned.pid),'/T','/F'],capture_output=True,timeout=10)
                else:owned.kill()
            if application_handle:application_handle.force_cleanup()
            owned.wait(timeout=10)
            raise RuntimeError('Clean application shutdown failed; cleanup is NOT a pass. '+str(error)) from error
        finally:
            if application_handle:application_handle.close();application_handle=None
            if owned.stdin and not owned.stdin.closed:owned.stdin.close()
            process=None
            if output_stream:output_stream.close();output_stream=None

    try:
        if (ROOT/'.env').exists():raise RuntimeError('Use a fresh extracted directory without .env; existing configuration is not modified')
        manifest_path=ROOT/'package-manifest.json'
        if manifest_path.is_file():
            manifest=json.loads(manifest_path.read_text(encoding='utf8'))
            for name,digest in manifest['files'].items():
                source=(ROOT/name).resolve()
                if not source.is_relative_to(ROOT) or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
                    raise RuntimeError('Extracted source does not match package manifest')
            summary['source_commit']=manifest['source_commit'];passed('package source hashes')
        node=shutil.which('node')
        if not node:raise RuntimeError('Install Node.js 24 LTS, reopen this terminal, then run the check again')
        summary['node']=check('node-version',[node,'--version']).stdout.strip()
        if not args.venv:
            check('fresh-setup',[sys.executable,'-B','run.py','--venv',environment,'setup'])
        else:
            check('existing-rehearsal-environment',[python,'-m','pip','check'])
        passed('fresh Windows virtual environment' if not args.venv else 'existing Linux rehearsal environment')
        launcher=[ROOT/'start.cmd','--venv',environment] if native_windows else [python,'-B',ROOT/'run.py','--venv',environment]
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
        url=f'http://127.0.0.1:{port}/'
        check('explicit-init',launcher+['init-demo','--database',database,'--port',port])
        before=database.read_bytes()
        repeat=check('repeat-init',launcher+['init-demo','--database',database],allow_failure=True)
        if repeat.returncode!=2 or before!=database.read_bytes():raise RuntimeError('Repeat init changed data or returned the wrong status')
        passed('actual launcher init and repeated-init rejection')
        health=launch(launcher+['serve','--database',database,'--port',port])
        summary['application']=health['app_version']
        if before!=database.read_bytes():raise RuntimeError('Serving unexpectedly wrote or seeded the database')
        passed('actual start.cmd service and health, no startup writes' if native_windows
               else 'Linux run.py service and health, no startup writes')
        cookies=CookieJar();client=build_opener(HTTPCookieProcessor(cookies))
        request=Request(url+'api/v1/auth/demo-session',data=json.dumps({'demo_account_id':'demo-patient-a'}).encode(),
                        headers={'Content-Type':'application/json','Origin':url.rstrip('/'),'Idempotency-Key':str(uuid.uuid4())})
        with client.open(request,timeout=10) as response:
            if response.status!=201:raise RuntimeError('Protected demo login failed')
        protected=check('native-protection',[python,'-B','-c',
            "from medplatform.protection import protect,unprotect; from medplatform.errors import AppError; "
            "p=protect(b'fictional acceptance payload','windows-acceptance'); "
            "assert unprotect(p,'windows-acceptance')==b'fictional acceptance payload'; print('protected round-trip passed')"])
        passed('native Windows DPAPI' if native_windows else 'Linux AES-GCM rehearsal, NOT DPAPI')
        stop();launch(launcher+['serve','--database',database,'--port',port])
        with client.open(url+'api/v1/auth/me',timeout=10) as response:
            if json.load(response)['data']['account']['account_id']!='demo-patient-a':raise RuntimeError('Original protected session was not recovered')
        passed('same-database restart restores original protected session')
        browser_package=args.browser_package
        if not browser_package:
            npm=shutil.which('npm.cmd' if native_windows else 'npm')
            if not npm:raise RuntimeError('npm from Node.js is required for isolated browser tooling')
            browser_package=run_dir/'browser-tools'
            check('browser-tooling',[npm,'install','--prefix',browser_package,'--no-audit','--no-fund','--ignore-scripts','playwright@1.62.1'])
        executable=args.browser_executable
        if not executable:
            candidates=[Path(os.environ.get(k,'C:/Program Files'))/p for k,p in (
                ('ProgramFiles(x86)','Microsoft/Edge/Application/msedge.exe'),('ProgramFiles','Microsoft/Edge/Application/msedge.exe'),
                ('ProgramFiles','Google/Chrome/Application/chrome.exe'),('LOCALAPPDATA','Google/Chrome/Application/chrome.exe'))]
            executable=next((p for p in candidates if p.is_file()),None)
        if not executable or not executable.is_file():raise RuntimeError('Install Microsoft Edge or Chrome; no browser substitute is used')
        browser_config=run_dir/'browser-config.json';browser_output=run_dir/'browser-result.json'
        browser_config.write_text(json.dumps(dict(url=url,browser_package=str(browser_package.resolve()),
            browser_executable=str(executable.resolve()),output=str(browser_output)),ensure_ascii=False),encoding='utf8')
        browser_run=check('system-browser',[node,ROOT/'scripts/acceptance_browser.cjs',browser_config],timeout=300,allow_failure=True)
        browser=json.loads(browser_output.read_text(encoding='utf8')) if browser_output.exists() else {}
        if browser_run.returncode or not browser.get('success') or browser.get('pageErrors'):
            summary['browser_failure']=dict(step=browser.get('current_step','before browser result'),
                error=browser.get('error',(browser_run.stderr or 'Browser result missing')[-1800:]),
                notice=browser.get('page_notice',''),passed_groups=len(browser.get('steps',[])),
                requests=browser.get('requests',[])[-12:])
            raise RuntimeError('System browser failed at '+summary['browser_failure']['step']+': '+summary['browser_failure']['error'])
        summary['browser']={key:browser[key] for key in ('success','browserVersion','platform')}
        summary['browser']['groups']=len(browser['steps']);passed('actual system browser: five pages, mobile layout, single_pass and STAR')
        stop()
        check('explicit-worker',launcher+['worker','--database',database,'--port',port,'--once'])
        passed('explicit worker finishes, web does not start worker')
        old=run_dir/'legacy.sqlite3'
        old_env=env.copy();env['DATABASE_PATH']=str(old)
        check('old-schema-init',[python,'-B','-m','medplatform','init-db','--target','14'])
        env.clear();env.update(old_env)
        with closing(sqlite3.connect(old)) as connection:
            connection.execute("INSERT INTO o_accounts VALUES ('windows-fixture','fictional retained account',NULL,0,NULL)")
            connection.commit()
        original=fingerprints(old)
        check('old-schema-upgrade',launcher+['migrate','--database',old,'--stopped','--output',run_dir/'backups'])
        upgraded=fingerprints(old)
        if not all(upgraded[name]==value for name,value in original.items()):raise RuntimeError('Legacy business rows changed in migration')
        with closing(sqlite3.connect(old)) as connection:
            fixture=connection.execute("SELECT display_name FROM o_accounts WHERE account_id='windows-fixture'").fetchone()
            if fixture!=('fictional retained account',):raise RuntimeError('Committed legacy fixture missing after migration')
        summary['old_tables_preserved']=len(original);passed('backup then 0014-to-0016 upgrade retains legacy rows')
        tests=check('full-regression',launcher+['test'],allow_failure=True,timeout=1800)
        text=tests.stdout+'\n'+tests.stderr
        if tests.returncode:
            summary['regression_failure']=dict(returncode=tests.returncode,diagnostic_tail=text[-12000:])
            raise RuntimeError('full-regression failed; see regression_failure in RESULT.json and full-regression.log')
        count=re.search(r'Ran (\d+) tests',text);skips=re.search(r'OK \(skipped=(\d+)\)',text)
        if not count or not re.search(r'^OK(?: \(skipped=\d+\))?$',text,re.M):raise RuntimeError('Full test completion evidence missing')
        summary['tests']=dict(run=int(count[1]),failures=0,errors=0,skipped=int(skips[1]) if skips else 0)
        passed('complete regression; actual skips reported')
        summary['status']='passed' if native_windows and not args.rehearsal else 'rehearsal_passed_not_windows'
        exit_code=0
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        summary['status']='failed';summary['error']=str(error);print('[FAILED] '+str(error),flush=True)
    finally:
        try:stop()
        except (OSError,RuntimeError,subprocess.SubprocessError) as error:
            summary['status']='failed';summary['shutdown_error']=str(error);exit_code=2
        summary['completed_at']=datetime.now(timezone.utc).isoformat()
        result=run_dir/'RESULT.json';result.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('RESULT_FILE='+str(result),flush=True)
        print('WINDOWS_ACCEPTANCE_RESULT='+json.dumps(summary,ensure_ascii=False),flush=True)
    return exit_code


if __name__=='__main__':
    raise SystemExit(main())
