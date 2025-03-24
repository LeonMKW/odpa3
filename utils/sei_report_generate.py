import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak, Image, Frame,
                                PageTemplate)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors

# Register Chinese font
pdfmetrics.registerFont(TTFont('SimSun', 'fonts/simsun.ttc', subfontIndex=0))

chinese_style = ParagraphStyle(
    name='Chinese',
    fontName='SimSun',
    fontSize=12,
    alignment=1,  # center alignment
)


def get_solar_status(value):
    if value is None or value == "暂无数据":
        return Paragraph("暂无数据", chinese_style)
    value = float(value)
    if value <= 100:
        img = Image('resources/solar-green.png', width=15, height=15)
        txt = "低"
    elif 100 < value <= 150:
        img = Image('resources/solar-yellow.png', width=15, height=15)
        txt = "中等"
    elif 150 < value <= 240:
        img = Image('resources/solar-orange.png', width=15, height=15)
        txt = "高"
    else:
        img = Image('resources/solar-red.png', width=15, height=15)
        txt = "极高"

    return Table([[img, Paragraph(txt, chinese_style)]], style=[
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
        ('BOX', (0, 0), (-1, -1), 0, colors.white),
    ])


def get_geomagnetic_status(value):
    if value is None or value == "暂无数据":
        return Paragraph("暂无数据", chinese_style)
    value = float(value)
    if value <= 15:
        img = Image('resources/lightning-green.png', width=15, height=15)
        txt = "平静微扰"
    elif 15 < value <= 20:
        img = Image('resources/lightning-yellow.png', width=15, height=15)
        txt = "中度扰动"
    elif 20 < value <= 30:
        img = Image('resources/lightning-orange.png', width=15, height=15)
        txt = "强扰动至小地磁暴"
    else:
        img = Image('resources/lightning-red.png', width=15, height=15)
        txt = "中等到大的磁暴级别"

    return Table([[img, Paragraph(txt, chinese_style)]], style=[
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
        ('BOX', (0, 0), (-1, -1), 0, colors.white),
    ])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('SimSun', 12)
    canvas.setStrokeColor(colors.red)
    canvas.setLineWidth(2)
    canvas.line(inch, inch + 30, A4[0] - inch, inch + 30)
    canvas.drawString(inch, inch + 10, "单位：银河航天测运控中心 GalaxySpace Mission Operations Center")
    canvas.drawRightString(A4[0] - inch, inch + 10, f"第{doc.page}页")
    canvas.restoreState()


def create_space_weather_report(filename, report_data):
    doc = SimpleDocTemplate(filename, pagesize=A4,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch + 50)

    chinese_style = ParagraphStyle(
        name='Chinese',
        fontName='SimSun',
        fontSize=14,
        leading=20,
    )

    chinese_title_style = ParagraphStyle(
        name='ChineseTitle',
        fontName='SimSun',
        fontSize=18,
        leading=22,
        alignment=1,
    )

    story = []

    # Logo at top-left
    logo_path = os.path.join('resources', 'yhhtlogo.png')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=80, height=80)
        logo.hAlign = 'LEFT'
        story.append(logo)
        story.append(Spacer(1, 20))

    # Title
    story.append(Paragraph(
        f"银河航天长管卫星轨道和空间环境{report_data['timeofday']}",
        chinese_title_style))
    story.append(Spacer(1, 10))

    # Report Generation Time (Centered)
    centered_style = ParagraphStyle(name='centered', fontName='SimSun', fontSize=14, alignment=1, textColor=colors.red)
    story.append(Paragraph(
        f"报告生成时间: {report_data['eventTimeStr']}",
        centered_style))
    story.append(Spacer(1, 10))

    # Longer and thicker Red line
    story.append(Spacer(1, 5))
    story.append(
        Paragraph("<para align='center'><font color='red' size='30'>_____________________________</font></para>",
                  chinese_style))
    story.append(Spacer(1, 40))

    # Space weather summary table
    space_env = report_data['space_env_data']

    solar_today = get_solar_status(space_env.get('F107_today'))
    solar_tomorrow = get_solar_status(space_env.get('F107_tomorrow'))
    geo_today = get_geomagnetic_status(space_env.get('Ap_today'))
    geo_tomorrow = get_geomagnetic_status(space_env.get('Ap_tomorrow'))

    summary_data = [
        ["", "太阳活动", "地磁活动"],
        ["过去12小时总结", solar_today, geo_today],
        ["未来12小时预测", solar_tomorrow, geo_tomorrow]
    ]

    summary_table = Table(summary_data, colWidths=[100, 150, 150], rowHeights=50)
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'SimSun'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Space Environment Data
    env_summary = (
        f"过去12小时F10.7指数: {space_env['past12hoursF107']}<br/>"
        f"过去12小时Kp指数: {space_env['past12hoursKp']}<br/>"
        f"过去12小时Ap指数: {space_env['past12hoursAp']}<br/>"
        f"未来12小时F10.7指数预测: {space_env['future12hoursF107']}<br/>"
        f"未来12小时Ap指数预测: {space_env['future12hoursAp']}<br/>"
        f"空间环境建议: {space_env['advisory']}"
    )
    story.append(Paragraph(env_summary, chinese_style))
    story.append(Spacer(1, 20))

    # Satellite Data Table
    satellite_data = report_data['satellite_data']
    data = [
        ["卫星代号", "对比开始时间", "均方误差", "星历误差", "轨道差值", "平均高度", "高度变化"]
    ]
    for sat in satellite_data:
        epoch_time = sat['epochTimeUTC'].replace(" ", "<br/>")
        epoch_paragraph = Paragraph(f"<para align='center'>{epoch_time}</para>", chinese_style)
        data.append([
            sat['code'],
            epoch_paragraph,
            f"{sat['mse']}米",
            f"{sat['ephemeris_error']}米",
            f"{sat['difference']}米",
            f"{sat['mean_altitude']}公里",
            f"{sat['altitude_change']}米"
        ])

    table = Table(data, colWidths=[60, 100, 60, 60, 60, 60, 60], rowHeights=50)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'SimSun'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)
    story.append(Spacer(1, 40))

    # 数据来源和标准
    story.append(Paragraph("<b>数据来源和标准:</b>", chinese_style))
    story.append(Spacer(1, 10))
    sources = [
        ('中国科学院空间环境预报中心', 'http://www.sepc.ac.cn/'),
        ('国家卫星气象中心太阳活动水平分级', 'https://std.samr.gov.cn/gb/search/gbDetailed?id=B2DA8771EDB59963E05397BE0A0A3389'),
        ('国家卫星气象中心地磁活动水平分级', 'https://std.samr.gov.cn/gb/search/gbDetailed?id=E116673ED4ECA3B7E05397BE0A0AC6BF'),
        ('银河轨道精度中心',
         'https://grafana10.galaxyspaceai.com/d/d78b50e2-b8fb-4852-96b0-2faf03274cfc/orbit-precision-prod?orgId=1'),
    ]
    for name, link in sources:
        story.append(Paragraph(f"• <a href='{link}' color='blue'>{name}</a>", chinese_style))
        story.append(Spacer(1, 5))

    story.append(Spacer(1, 20))

    # 备注
    story.append(Paragraph("<b>备注:</b>", chinese_style))
    remarks = """
    <b>• F10.7-太阳活动水平:</b><br/>
         <70非常低；70-100低；100-150中等；150-200高；200+极高(接近太阳活动峰值)<br/><br/>

    <b>• Kp指数-地磁活动强度:</b><br/>
         0-1平静；2-3稍有扰动；4活跃；5小地磁暴(G1)；6中等地磁暴(G2)；7强烈地磁暴(G3)；8严重地磁暴(G4)；9极端地磁暴(G5)<br/><br/>

    <b>• Ap指数-地磁扰动状态:</b><br/>
         0-7平静；8-15轻度扰动；16-29活跃；30-49小地磁暴；50-99大地磁暴；100+极端地磁暴<br/><br/>

    • 12小时外推误差的计算方式为从星历历元时间开始，外推计算12小时轨道数据，拟合后算出绝对距离，并与卫星同一时间段实际GNSS数据拟合后算出绝对距离之间的差值。其反映了理论和实际轨道的整体偏离情况。<br/><br/>

    • 定轨误差为星历历元时间时刻或实际GNSS数据第一点时间时刻理论与实际距离差值。其反映了星历的误差。
    """
    story.append(Paragraph(remarks, chinese_style))

    # Build PDF with footer on each page
    doc.build(story, onLaterPages=footer)

# create_space_weather_report("space_weather_report_fixed.pdf", report_data)
