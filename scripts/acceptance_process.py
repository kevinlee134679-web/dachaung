"""Observe the owned application separately from a Windows batch-file wrapper."""
import ctypes
from ctypes import wintypes
import re
import subprocess
import time


def application_pid(log_segment):
    matches=re.findall(r'Started server process \[(\d+)\]',log_segment)
    if not matches:
        raise RuntimeError('The owned application PID is missing from this launch log')
    return int(matches[-1])


class WindowsApplication:
    """A handle to this launch's server, so PID reuse cannot change our target."""
    def __init__(self,pid):
        self.pid=pid
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        self.kernel.OpenProcess.restype=wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype=wintypes.DWORD
        self.kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
        self.kernel.TerminateProcess.restype=wintypes.BOOL
        self.kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        self.kernel.CloseHandle.restype=wintypes.BOOL
        self.handle=self.kernel.OpenProcess(0x100000|0x1000|0x0001,False,pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def has_exited(self):
        result=self.kernel.WaitForSingleObject(self.handle,0)
        if result==0:return True
        if result==258:return False
        raise ctypes.WinError(ctypes.get_last_error())

    def force_cleanup(self):
        # Failure cleanup only. This action must never turn an acceptance into a pass.
        if not self.has_exited() and not self.kernel.TerminateProcess(self.handle,2):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle=None


def wait_for_shutdown(probe,*,timeout=20,poll=.1):
    """A closed port or a log line alone cannot prove clean application exit."""
    deadline=time.monotonic()+timeout
    while True:
        evidence=probe()
        if all(evidence.get(key) is True for key in ('application_exited','port_closed','shutdown_log_complete')):
            return evidence
        if time.monotonic()>=deadline:
            raise RuntimeError('Application shutdown was not verified: '+str(evidence))
        time.sleep(poll)


def release_idle_wrapper(process,*,application_verified_stopped,timeout=3):
    """Only close an idle shell after the actual application has cleanly exited."""
    if not application_verified_stopped:
        raise RuntimeError('Refusing to treat wrapper cleanup as application shutdown')
    if process.poll() is not None:return 'already_exited'
    # cmd.exe can wait for "Terminate batch job (Y/N)?" after the child exits.
    if process.stdin:
        try:
            process.stdin.write(b'Y\r\n')
            process.stdin.flush()
            process.stdin.close()
        except (BrokenPipeError,OSError,ValueError):
            pass
    try:
        process.wait(timeout=timeout)
        return 'batch_confirmation_released'
    except subprocess.TimeoutExpired:
        # The server is already gone. Terminate only our otherwise idle wrapper,
        # never its tree and never the application as a successful stop strategy.
        process.terminate()
        process.wait(timeout=timeout)
        return 'idle_wrapper_closed_after_verified_application_exit'
