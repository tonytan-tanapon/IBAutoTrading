# IB Auto Trading

โปรเจกต์เริ่มต้นสำหรับทดลอง Auto Trading กับ Interactive Brokers ผ่าน TWS API
โดยตั้งค่าเริ่มต้นให้ทำงานแบบ `dry-run` และควรใช้กับ Paper Trading เท่านั้น

> ซอฟต์แวร์นี้เป็นตัวอย่างทางเทคนิค ไม่ใช่คำแนะนำการลงทุน

## สิ่งที่บอตทำ

- ดึงแท่งราคารายวันจาก IBKR
- คำนวณ Simple Moving Average (SMA) ระยะสั้นและระยะยาว
- ส่งสัญญาณซื้อเมื่อ SMA ระยะสั้นตัดขึ้น
- ส่งสัญญาณขายเมื่อ SMA ระยะสั้นตัดลง
- ไม่เปิดสถานะ short
- จำกัดจำนวนหุ้นต่อคำสั่งด้วย `IB_QUANTITY`
- ไม่ส่งคำสั่งจริงจนกว่าจะตั้ง `IB_ALLOW_ORDERS=true`
- ปฏิเสธการส่งคำสั่งถ้าบัญชีไม่ใช่ Paper Account (`DU...`)

## 1. เตรียมระบบ

ติดตั้ง Python 3.11 ขึ้นไป จากนั้นสร้าง virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. ตั้งค่า TWS

1. เปิด TWS และเข้าสู่ระบบ **Paper Trading**
2. ไปที่ `File > Global Configuration > API > Settings`
3. เปิด `Enable ActiveX and Socket Clients`
4. ตรวจว่า Socket port เป็น `7497`
5. ระหว่างทดสอบครั้งแรก แนะนำให้เปิด `Read-Only API`

พอร์ตที่ใช้บ่อย:

- TWS Paper: `7497`
- TWS Live: `7496`
- IB Gateway Paper: `4002`
- IB Gateway Live: `4001`

## 3. ตั้งค่าโปรแกรม

คัดลอก `.env.example` เป็น `.env` แล้วแก้ค่าตามต้องการ:

```powershell
Copy-Item .env.example .env
```

ค่าเริ่มต้นจะดูสัญญาณของ `SPY` ด้วย SMA 5/20 วัน และจะ **ไม่ส่งออเดอร์**

## 4. ทดลองรัน

```powershell
python -m ib_auto_trading
```

หากการเชื่อมต่อและสัญญาณถูกต้อง โปรแกรมจะแสดง `DRY RUN` แทนการส่งคำสั่ง

เมื่อตรวจสอบบน Paper Account เรียบร้อยแล้ว:

```env
IB_ALLOW_ORDERS=true
```

จากนั้นปิด `Read-Only API` ใน TWS และรันใหม่ โปรแกรมจะยังตรวจว่าหมายเลขบัญชีขึ้นต้น
ด้วย `DU` ก่อนส่งออเดอร์

## ทดสอบโค้ด

```powershell
python -m unittest discover -s tests -v
```

## ขั้นต่อไปก่อนใช้เงินจริง

- เก็บประวัติสัญญาณ ออเดอร์ และ execution ลงฐานข้อมูล
- เพิ่ม stop loss, daily loss limit และ kill switch
- ตรวจ market hours และวันหยุดตลาด
- ทำ backtest รวม commission และ slippage
- เพิ่มการแจ้งเตือนเมื่อ disconnect หรือ order ถูก reject

เอกสารอ้างอิง: [IBKR TWS API Documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)
