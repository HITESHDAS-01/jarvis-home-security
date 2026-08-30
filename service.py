import sys
import os
import time
import subprocess
import threading

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


if HAS_WIN32:
    class JarvisService(win32serviceutil.ServiceFramework):
        _svc_name_ = "JarvisHome"
        _svc_display_name_ = "JARVIS Home Security System"
        _svc_description_ = "AI-powered home security assistant with CCTV monitoring"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.process = None
            self.running = True

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.running = False
            if self.process:
                self.process.terminate()
            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ''),
            )
            self.main()

        def main(self):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            main_script = os.path.join(script_dir, "main.py")

            while self.running:
                try:
                    self.process = subprocess.Popen(
                        [sys.executable, main_script],
                        cwd=script_dir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    self.process.wait()
                    if self.running:
                        time.sleep(10)
                except Exception as e:
                    servicemanager.LogErrorMsg(f"Jarvis Service Error: {e}")
                    time.sleep(30)


if __name__ == "__main__":
    if not HAS_WIN32:
        print("This module requires pywin32. Install with: pip install pywin32")
        sys.exit(1)
    if len(sys.argv) == 1:
        servicemanager.PrepareToHostSingle(JarvisService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(JarvisService)
