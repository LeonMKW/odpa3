import pytz
from datetime import datetime
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import re

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
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=inch, leftMargin=inch,
        topMargin=inch, bottomMargin=inch
    )

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
            # Include windgust in the text
            cc_text = (
                f"<b>当前状况:</b><br/>"
                f"气温: {cc.get('temp')}℃; 湿度: {cc.get('humidity')}%<br/>"
                f"风速: {cc.get('windspeed')} km/h; 平均: {cc.get('B_wind_scale')}级 ({cc.get('B_wind_scale_chinese')})<br/>"
                f"阵风: {cc.get('windgust')} km/h; 阵风风力: {cc.get('B_wind_gust_scale')}级 ({cc.get('B_wind_gust_scale_chinese')})<br/>"
                f"天气: {cc.get('conditions')}<br/>"
                f"降水: {cc.get('precip', '0.0')} mm ({cc.get('precipitation_scale', '无雨')})"
            )

        story.append(Paragraph(cc_text, styles["default"]))
        story.append(Spacer(1, 12))

        # Show alerts:
        # Now that you have separate lists for windspeed, windgust, and rain,
        # read them individually instead of lumps of wind vs. rain.
        alerts = st_data.get("alerts", {})
        windspeed_alerts = alerts.get("windspeed", [])
        windgust_alerts = alerts.get("windgust", [])
        rain_alerts = alerts.get("rain", [])

        # The lists for alerts that specifically fall within tasks:
        # (If you use them, keep them or adapt similarly)
        wind_during_task = st_data.get("wind_during_task", [])
        rain_during_task = st_data.get("rain_during_task", [])

        # If no "standard" alerts:
        if not windspeed_alerts and not windgust_alerts and not rain_alerts:
            story.append(Paragraph("<b>预警情况：</b>无预警", styles["default"]))
        else:
            # Windspeed alerts
            if windspeed_alerts:
                story.append(Paragraph("<b>平均风速预警：</b>", styles["default"]))
                for walert in windspeed_alerts:
                    story.append(Paragraph(f"• {walert}", styles["default"]))
                story.append(Spacer(1, 6))

            # Windgust alerts
            if windgust_alerts:
                story.append(Paragraph("<b>阵风预警：</b>", styles["default"]))
                for galert in windgust_alerts:
                    story.append(Paragraph(f"• {galert}", styles["default"]))
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

            # Optionally add windgust columns if you'd like to show them in the table
            data = [
                ["时间", "温度(℃)", "风速(km/h)", "风力", "阵风(km/h)", "阵风风力", "降水(mm)", "天气"]
            ]

            for hour in day.get("hours", []):
                # We'll add separate columns for windgust
                row = [
                    hour.get("datetime"),
                    hour.get("temp"),
                    hour.get("windspeed"),
                    f"{hour.get('B_wind_scale_chinese')}({hour.get('B_wind_scale')})",
                    hour.get("windgust", 0),
                    f"{hour.get('B_wind_gust_scale_chinese', '')}({hour.get('B_wind_gust_scale', '')})",
                    f"{hour.get('precip', 0)}({hour.get('precipitation_scale', '无雨')})",
                    hour.get("conditions")
                ]
                data.append(row)

            # Adjust columns for 8 columns
            table = Table(data, colWidths=[60, 60, 60, 80, 60, 80, 80, 80])
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


def plot_all_stations_weather_snapshot(weather_data, output_folder, OSS2):

    # Force a Chinese‐compatible font so that characters (e.g. 大风) show properly.
    matplotlib.rcParams['font.sans-serif'] = ['SimSun']
    matplotlib.rcParams['axes.unicode_minus'] = False

    rows = []
    bj_tz = pytz.timezone("Asia/Shanghai")

    for station_code, station_data in weather_data.items():
        for day in station_data.get("days", []):
            day_str = day.get("datetime", "")
            hours_list = day.get("hours", [])
            for hr in hours_list:
                full_time_str = f"{day_str} {hr.get('datetime', '00:00:00')}"
                try:
                    dt_obj = datetime.strptime(full_time_str, "%Y-%m-%d %H:%M:%S")
                    dt_obj = bj_tz.localize(dt_obj)
                except ValueError:
                    continue

                rows.append({
                    "station": station_code,
                    "time": dt_obj,
                    "temp": hr.get("temp", ""),
                    # Use the numeric gust value from B_wind_gust_scale for alerting
                    "windgust": hr.get("B_wind_gust_scale", ""),
                    # Chinese description of the gust level; not used for numeric alerting.
                    "b_wind_gust_scale_chinese": hr.get("B_wind_gust_scale_chinese", ""),
                    "precip": hr.get("precip", ""),
                    "precip_scale": hr.get("precipitation_scale", ""),
                    "conditions": hr.get("conditions", "")
                })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df.sort_values(by=["station", "time"], inplace=True)

    # Convert time to a string for the table
    df["time_str"] = df["time"].dt.strftime("%m-%d %H:%M")

    # Build the table data array in the order you specified:
    # 0: Station, 1: Time, 2: Temp(°C), 3: 阵风等级, 4: 阵风风力, 5: 降水(mm), 6: 降水程度, 7: 天气
    col_labels = [
        "信关站",
        "时段",
        "气温(°C)",
        "阵风等级",
        "阵风风力",
        "降水(mm)",
        "降水程度",
        "天气"
    ]
    table_data = []
    for _, row in df.iterrows():
        table_data.append([
            row["station"],
            row["time_str"],
            row["temp"],
            row["windgust"],  # numeric gust value (as stored)
            row["b_wind_gust_scale_chinese"],  # Chinese description of gust level
            row["precip"],
            row["precip_scale"],
            row["conditions"]
        ])

    # Create a figure with an axis for the table; height adjusts based on number of rows.
    fig, ax = plt.subplots(figsize=(12, 0.4 * len(table_data) + 2))
    ax.set_axis_off()
    the_table = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="upper center"
    )
    the_table.auto_set_font_size(False)
    the_table.set_fontsize(10)
    plt.title("各信关站气象预报快照", pad=20)

    num_data_rows = len(table_data)
    for i in range(num_data_rows):
        # Check the '阵风等级' cell in column index 3
        gust_numeric_str = table_data[i][3]
        try:
            scale_val = int(str(gust_numeric_str).strip())
        except ValueError:
            scale_val = 0  # if not convertable, default to 0

        if scale_val >= 6:
            the_table[i + 1, 3].set_facecolor(color='red')

        # Check precipitation cell in column index 5.
        precip_str = table_data[i][5]
        try:
            precip_val = float(str(precip_str).strip())
        except ValueError:
            precip_val = 0.0

        if precip_val >= 100:
            the_table[i + 1, 5].set_facecolor(color='red')
        elif precip_val >= 50:
            the_table[i + 1, 5].set_facecolor(color='orange')
        elif precip_val >= 25:
            the_table[i + 1, 5].set_facecolor(color='yellow')
        elif precip_val > 0:
            the_table[i + 1, 5].set_facecolor(color='#90EE90')

    plt.tight_layout()
    plt.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)

    # Force a draw so the table is rendered
    fig.canvas.draw()
    # Get the bounding box of the table in inches
    table_bbox = the_table.get_window_extent(fig.canvas.get_renderer()).transformed(fig.dpi_scale_trans.inverted())

    snapshot_filename = f"allstations_weather_snapshot_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    local_path = os.path.join(output_folder, snapshot_filename)
    plt.savefig(local_path, bbox_inches=table_bbox, pad_inches=0.5, dpi=240)
    plt.close(fig)


    oss_key = f"weather-snapshots/{snapshot_filename}"
    OSS2.upload_file(oss_key, local_path)
    snapshot_url = OSS2.make_url(oss_key)
    os.remove(local_path)

    return snapshot_url
