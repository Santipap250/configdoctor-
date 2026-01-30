def analyze(size, battery, style):
    advice = []

    size = int(size)

    if size >= 5:
        advice.append("เหมาะกับการปรับ PID แบบไม่แข็งเกิน เพื่อประหยัดมอเตอร์")
    else:
        advice.append("โดรนเล็ก ควรเน้น Filter มากกว่าดัน PID")

    if battery == "6S":
        advice.append("แนะนำ Throttle Limit 85–90% ลด heat")
    else:
        advice.append("4S คุม Throttle curve ให้เนียน จะบินได้นานขึ้น")

    if style == "freestyle":
        advice.append("ลด D-term นิดหน่อย จะคุมคันง่าย")
    elif style == "longrange":
        advice.append("เพิ่ม Filter + ลด RPM noise จะประหยัดแบต")
    else:
        advice.append("เน้น Smooth → ลด Feedforward")

    return "\n".join(f"- {x}" for x in advice)