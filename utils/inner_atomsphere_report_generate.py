import os
import io
import time
import pytz
import json
import requests
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, Spacer, SimpleDocTemplate, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
# If you want Chinese fonts, register SimSun etc:
# pdfmetrics.registerFont(TTFont('SimSun', 'SimSun.ttf'))
# addMapping('SimSun', 0, 0, 'SimSun')
# from .db import OSS2  # if you have a class for Alibaba Cloud OSS

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, PageBreak
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import inch
from reportlab.lib import colors
import os

# Register the Chinese font
pdfmetrics.registerFont(TTFont('SimSun', 'fonts/simsun.ttc', subfontIndex=0))

# Define Chinese paragraph styles
styles = {
    "default": ParagraphStyle(
        "default",
        fontName="SimSun",
        fontSize=12,
        leading=15,
    ),
    "title": ParagraphStyle(
        "title",
        fontName="SimSun",
        fontSize=16,
        textColor=colors.red,
        leading=20,
        alignment=1,  # Centered
    ),
    "table": ParagraphStyle(
        "table",
        fontName="SimSun",
        fontSize=11,
        alignment=1,  # Centered
    )
}


# Function to create the PDF
def create_weather_forecast_pdf(pdf_path, weather_data):
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)

    story = []

    for station_key, st_data in weather_data.items():
        # Get current Beijing time
        beijing_tz = pytz.timezone('Asia/Shanghai')
        current_time_beijing = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

        # Station title
        station_title = Paragraph(f"天气预报：{current_time_beijing} - {station_key}", styles["title"])
        story.append(station_title)
        story.append(Spacer(1, 12))

        # Station info
        station_info = (
            f"站点名称: {st_data.get('antenna_name')}<br/>"
            f"经纬度: {st_data.get('latitude')}, {st_data.get('longitude')}<br/>"
            f"时区: {st_data.get('timezone')}<br/>"
        )
        story.append(Paragraph(station_info, styles["default"]))
        story.append(Spacer(1, 12))

        # Current conditions
        cc = st_data.get("currentConditions", {})
        if isinstance(cc, str):
            # If cc is "未查询到结果" or any other string, just show the string.
            cc_text = f"<b>当前状况:</b><br/>{cc}"
        else:
            # cc is presumably a dictionary
            cc_text = (
                f"<b>当前状况:</b><br/>"
                f"气温: {cc.get('temp')}℃; 湿度: {cc.get('humidity')}%<br/>"
                f"风速: {cc.get('windspeed')} km/h; 风力: {cc.get('B_wind_scale')}级 ({cc.get('B_wind_scale_chinese')})<br/>"
                f"天气: {cc.get('conditions')}<br/>"
                f"降水: {cc.get('precip', '0.0')} mm ({cc.get('precipitation_scale', '无雨')})"
            )

        story.append(Paragraph(cc_text, styles["default"]))
        story.append(Spacer(1, 12))

        # Show alerts: separate wind vs. rain
        alerts = st_data.get("alerts", {})
        wind_alerts = alerts.get("wind", [])
        rain_alerts = alerts.get("rain", [])

        # The lists for alerts that specifically fall within tasks:
        wind_during_task = st_data.get("wind_during_task", [])
        rain_during_task = st_data.get("rain_during_task", [])

        # If no "standard" alerts:
        if not wind_alerts and not rain_alerts:
            story.append(Paragraph("<b>预警情况：</b>无预警", styles["default"]))
        else:
            # Wind alerts
            if wind_alerts:
                story.append(Paragraph("<b>风力预警：</b>", styles["default"]))
                for walert in wind_alerts:
                    story.append(Paragraph(f"• {walert}", styles["default"]))
                story.append(Spacer(1, 6))

            # Rain alerts
            if rain_alerts:
                story.append(Paragraph("<b>降水预警：</b>", styles["default"]))
                for ralert in rain_alerts:
                    story.append(Paragraph(f"• {ralert}", styles["default"]))
                story.append(Spacer(1, 6))

        # Now show *during-task* wind/rain alerts
        if wind_during_task or rain_during_task:
            story.append(Spacer(1, 12))
            story.append(Paragraph("<b>在任务时间内的天气预警:</b>", styles["default"]))

            if wind_during_task:
                story.append(Paragraph("• <b>任务期间风力预警</b>", styles["default"]))
                for witem in wind_during_task:
                    w_time = witem["time"]
                    w_msg = witem["message"]
                    story.append(Paragraph(f"- {w_time} => {w_msg}", styles["default"]))

            if rain_during_task:
                story.append(Paragraph("• <b>任务期间降水预警</b>", styles["default"]))
                for ritem in rain_during_task:
                    r_time = ritem["time"]
                    r_msg = ritem["message"]
                    story.append(Paragraph(f"- {r_time} => {r_msg}", styles["default"]))

        story.append(Spacer(1, 12))
        # Forecast table per day
        for day in st_data.get("days", []):
            story.append(Paragraph(f"<b>日期: {day['datetime']}</b>", styles["default"]))

            data = [["时间", "温度(℃)", "风速(km/h)", "风力", "降水(mm)", "天气"]]

            for hour in day.get("hours", []):
                row = [
                    hour.get("datetime"),
                    hour.get("temp"),
                    hour.get("windspeed"),
                    f"{hour.get('B_wind_scale_chinese')}({hour.get('B_wind_scale')})",
                    f"{hour.get('precip', 0)}({hour.get('precipitation_scale', '无雨')})",
                    hour.get("conditions")
                ]
                data.append(row)

            table = Table(data, colWidths=[60, 60, 60, 80, 80, 80])
            table.setStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'SimSun'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
            ])

            story.append(table)
            story.append(Spacer(1, 12))

        story.append(PageBreak())

    doc.build(story)


