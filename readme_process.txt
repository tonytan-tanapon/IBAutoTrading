หลังจากกด Start Engine โปรแกรมทำงานตามลำดับนี้ครับ
1. หน้าเว็บส่งคำขอ:
POST /api/engine/start

2. เว็บตรวจว่า Engine กำลังรันอยู่หรือไม่
ถ้ารันอยู่แล้ว จะตอบ 409 Engine is already running เพื่อป้องกันการเชื่อมซ้ำ

3. สร้าง background thread
หน้าเว็บจึงยังใช้งานต่อได้ระหว่าง Engine ทำงาน

4. เชื่อมต่อ TWS
ใช้ค่าปัจจุบัน:
IB_HOST = "127.0.0.1"
IB_PORT = 7497
IB_CLIENT_ID = 0
โปรแกรมรอการเชื่อมต่อสูงสุด 10 วินาที

5. โหลดข้อมูลเริ่มต้น 5 รายการพร้อมกัน
Account summary
Positions
Open orders
Historical data ของ TSLA
Option chain ของ TSLA

Historical Data ใช้ค่าปัจจุบัน:
HISTORICAL_DURATION = "2 D"
HISTORICAL_BAR_SIZE = "30 mins"
HISTORICAL_TIMEOUT = 15
ถ้ารายการใดโหลดไม่สำเร็จ จะถือว่าการเริ่ม Engine ล้มเหลว และ disconnect

6. Subscribe ราคาสดของ TSLA
เมื่อข้อมูลเริ่มต้นครบ โปรแกรมเรียก Market Data ของ:
UNDERLYING_SYMBOL = "TSLA"
UNDERLYING_ASSET_TYPE = "stock"

7. เข้าโหมดทำงานต่อเนื่อง
ทุกครั้งที่ TWS ส่งราคาใหม่เข้ามา โปรแกรมจะ:
รับราคา
→ สร้าง Strategy context
→ คำนวณ Strategy snapshot
→ อ่าน BUY/SELL signal
→ ตรวจ Positions และ Open orders
→ ตรวจ Risk
→ เลือก Option contract
→ คำนวณราคาและจำนวนสัญญา
→ จัดการ Order
ถ้ารอบใดเกิด error ตอนคำนวณ Strategy หรือจัดการ Order โปรแกรมจะพิมพ์:
Processing error: ...
แล้วทำรอบต่อไปโดยไม่ disconnect


8. หน้าเว็บอ่านข้อมูลทุก 2 วินาที
หน้าเว็บเรียก:
GET /api/status
GET /api/dashboard
เพื่อแสดงสถานะ ราคา บัญชี Positions, Orders และ Strategy ล่าสุด การเรียกสอง API นี้ไม่ได้ส่ง Order

9. ตอนนี้ยังไม่ส่ง Order จริง
เพราะตั้งค่า:
DRY_RUN_ORDERS = True
ถ้ามีสัญญาณซื้อ โปรแกรมจะแสดงประมาณนี้ใน terminal:
DRY RUN: would submit option order

10. Engine หยุดเมื่อ:กด Stop Engine
TWS ปิด connection
การโหลดข้อมูลเริ่มต้น timeout
เกิด error ระหว่าง startup
ปิด web.bat

เมื่อหยุดจะเห็น:
TWS connection closed
Disconnected