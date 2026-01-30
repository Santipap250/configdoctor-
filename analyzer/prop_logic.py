def analyze_propeller(prop_size, prop_pitch, blade_count, style):
    result = {}

    noise_score = 0
    motor_load = 0
    efficiency = "กลาง"

    # วิเคราะห์ Pitch
    if prop_pitch >= 4.5:
        noise_score += 3
        motor_load += 3
        efficiency = "แรงจัด กินไฟ"
    elif prop_pitch >= 4.0:
        noise_score += 2
        motor_load += 2
        efficiency = "สมดุล"
    else:
        noise_score += 1
        motor_load += 1
        efficiency = "ประหยัด นุ่ม"

    # วิเคราะห์จำนวนใบ
    if blade_count == 4:
        noise_score += 3
        motor_load += 3
        grip = "หนึบมาก"
    elif blade_count == 3:
        noise_score += 2
        motor_load += 2
        grip = "หนึบดี"
    else:
        noise_score += 1
        motor_load += 1
        grip = "นุ่ม ลอย"

    # วิเคราะห์ตามสไตล์
    if style == "racing":
        recommend = "เหมาะกับ Racing ตอบสนองไว"
    elif style == "longrange":
        recommend = "เหมาะกับ Long Range, Smooth"
    else:
        recommend = "เหมาะกับ Freestyle, สมดุล"

    # สรุปผล
    result["summary"] = (
        f"ใบพัด {prop_size} นิ้ว {blade_count} ใบ Pitch {prop_pitch} | "
        f"Grip: {grip} | Efficiency: {efficiency}"
    )
    result["effect"] = {
        "noise": noise_score,
        "motor_load": motor_load,
        "efficiency": efficiency,
        "grip": grip
    }
    result["recommendation"] = recommend
    return result
