def analyze_battery(battery):
    if battery == "4S":
        return "แรงดัน 4S (14.8V) มาตรฐาน FPV"
    elif battery == "6S":
        return "แรงดัน 6S (22.2V) สำหรับแรงขับสูง"
    else:
        return "ไม่ทราบแบตเตอรี่"
