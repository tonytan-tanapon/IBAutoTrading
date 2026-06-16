import subprocess
import time
import pyautogui
import os

print(os.path.exists(r"C:\Jts\tws.exe"))
# เปิด TWS
subprocess.Popen(r"C:\Jts\tws.exe")

# รอโปรแกรมเปิด
time.sleep(10)

# กรอก username
pyautogui.write("tana2104")

# Tab ไป password
pyautogui.press("tab")

# กรอก password
pyautogui.write("tman1234")

# Enter login
pyautogui.press("enter")