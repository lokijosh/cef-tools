import re
import time
import pysyslogclient, datetime, argparse
from event import CEFEvent

client = pysyslogclient.SyslogClientRFC5424("127.0.0.1", "514", proto="UDP")
match_str = "([a-zA-Z]+\s\d{1,2}\s[0-9][0-9]:[0-9][0-9]:[0-9][0-9])\s([^ ]+)\s(%ASA[^: ]+):\s(.+)"
payload = {"deviceVendor": "Cisco", "deviceProduct": "ASA", "deviceFacility": "local4", "SourceSystem": "OpsManager"}
severity_table = {"1": "High", "2": "High", "3": "Medium", "4": "Medium"}


def send_cef(payload, spoof_host, syslog_msg):
    c = CEFEvent()
    for k, v in payload.items():
        c.set_field(k, v)
        cef_msg = c.build_cef()
    client.log(message=cef_msg, program="CEF", hostname=spoof_host)
    client.close()

def sys_to_cef(syslog_msg):
    ret = re.findall(match_str, syslog_msg)
    if ret:
        ret = ret[0]
        msg = ret[3]
        dt = ret[0]
        year = datetime.datetime.now().year
        dt_arr = dt.split(" ")
        fixed_dt = "{} {} {} {}".format(dt_arr[0], dt_arr[1], year, dt_arr[2])
        dt_obj = datetime.datetime.strptime(fixed_dt, "%b %d %Y %H:%M:%S")
        sev = ret[2].split("-")[1]
        payload["dvchost"] = ret[1] # DeviceName
        spoof_host = ret[1]
        payload["signatureId"] = ret[2].split("-")[-1] # DeviceEventClassID
        payload["severity"] = severity_table[sev] # LogSeverity
        #payload["OriginalLogSeverity"] = sev
        payload["message"] = "{}: {}".format(ret[2], ret[3])
        payload["DeviceAddress"] = ret[1]
        #payload["rt"] = time.time() * 1000
        payload["rt"] = datetime.datetime.today().strftime("%-m/%d/%Y %-I:%M:%S %p")
        # Deny UDP reverse path check from 135.89.112.113 to 32.246.198.2 on interface inside16
        #if re.match("(Deny)\s(.+6)\s(reverse)\s(path)\s(check)\s(from)\s(.+)\sto\s(.+)\s(on)\s(interface)\s(.+)", msg):
        if re.match("Deny\s.{,10}\sreverse\spath\scheck", msg):
            #print("MATCHED!")
            tmp = msg.split(" ")
            payload["dst"] = tmp[8]
            payload["proto"] = tmp[1]
            payload["sourceAddress"] = tmp[6]
            #payload["RemoteIP"] = tmp[6]
            payload["act"] = tmp[0] # DeviceAction
            #payload["simplifiedDeviceAction"] = tmp[0]
            #payload["deviceDirection"] = "0"
        else:
            print("Nothing else to parse")
        #print(payload)
        send_cef(payload, spoof_host, syslog_msg)
    #print(ret)


"""
def follow(thefile):
    thefile.seek(0,2)
    while True:
        line = thefile.readline()
        if not line:
            time.sleep(0.1)
            continue
        yield line
"""


"""
def follow(f, log_name):
    f.seek(0,2)
    inode = os.fstat(f.fileno()).st_ino
    while True:
        line = f.readline()
        if not line:
            time.sleep(0.1)
            try:
                if os.stat(log_name).st_ino != inode:
                    f.close()
                    f = open(log_name, "r")
                    inode = os.fstat(f.fileno()).st_ino
            except IOError:
                pass
            continue
        yield line
"""


if __name__ == "__main__":
    """
    log_name = "/var/log/asa/asa.log"
    logfile = open(log_name, "r")
    loglines = follow(logfile, log_name)
    for line in loglines:
        line = line.strip()
        sys_to_cef(line)
    """

    file_name = "/var/log/asa/asa.log"
    seek_end = True
    while True: # handle moved/truncated files by allowing to reopen
        with open(file_name) as f:
            if seek_end: # reopened files must not seek end
                f.seek(0, 2)
            while True: # line reading loop
                line = f.readline()
                if not line:
                    try:
                        if f.tell() > os.path.getsize(file_name):
                            # rotation occurred (copytruncate/create)
                            f.close()
                            seek_end = False
                            break
                    except FileNotFoundError:
                        # rotation occurred but new file still not created
                        pass # wait 1 second and retry
                    time.sleep(1)
                else:
                    #with open("out.txt", "a") as fw:
                    #    line = line.strip()
                    #    fw.write("{}\n".format(line))
                    sys_to_cef(line)
