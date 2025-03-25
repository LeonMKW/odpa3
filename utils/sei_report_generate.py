import os, io
import matplotlib

matplotlib.use('Agg')  # Required in headless environments
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle,
                                Spacer, Image)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib import colors
import time, json
import pytz
from datetime import datetime, timedelta

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


def create_space_weather_report(filename, report_data, raw_space_env_data):
    doc = SimpleDocTemplate(filename, pagesize=A4,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch + 50)
    """
    :param filename: The PDF filename to save
    :param report_data: Your normal 'report_data' dict (orbit data, etc.)
    :param raw_space_env_data: The 'space_weather_report_raw' return dict
                               containing 'full_F107', 'full_ApIndex', 'Kp_values', etc.
    """

    chinese_style = ParagraphStyle(
        name='Chinese',
        fontName='SimSun',
        fontSize=14,
        leading=20,
    )

    chinese_title_style = ParagraphStyle(
        name='ChineseTitle',
        fontName='SimSun',
        fontSize=24,
        leading=22,
        alignment=1,
    )

    chinese_paragraph_title_style = ParagraphStyle(
        name='ChineseTitle',
        fontName='SimSun',
        fontSize=16,
        leading=22,
        alignment=1,
    )

    story = []

    # --- 1) Logo
    logo_path = os.path.join('resources', 'yhhtlogo.png')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=80, height=80)
        logo.hAlign = 'LEFT'
        story.append(logo)
        story.append(Spacer(1, 20))

    # --- 2) Title
    story.append(Paragraph(
        f"银河航天卫星轨道和空间环境{report_data['timeofday']}",
        chinese_title_style))
    story.append(Spacer(1, 10))

    # --- 3) Report Generation Time (Centered)
    centered_style = ParagraphStyle(name='centered', fontName='SimSun', fontSize=14, alignment=1, textColor=colors.red)
    story.append(Paragraph(
        f"报告生成时间: {report_data['eventTimeStr']}",
        centered_style))
    story.append(Spacer(1, 5))

    # Immediately after your title or paragraph
    story.append(HRFlowable(width="100%", thickness=2, color=colors.red, spaceBefore=20, spaceAfter=20))

    # 新增段落标题

    story.append(Paragraph(
        f"空间环境",
        chinese_paragraph_title_style))
    story.append(Spacer(1, 15))

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

    #  ============= NEW: Generate F10.7 and Ap line plots =============

    def parse_md_to_datetime(md_string, year=2025):
        """
        Parses a 'MM-DD' string (e.g. '03-17') into a datetime with a default year.
        """
        return datetime.strptime(f"{year}-{md_string}", "%Y-%m-%d")

    # 1. Convert request_time to Beijing datetime
    request_time_ms = raw_space_env_data["space_env_data"].get("request_time")  # e.g. 1742400000000
    beijing_tz = pytz.timezone('Asia/Shanghai')
    if request_time_ms is None:
        request_dt_beijing = datetime.now(tz=beijing_tz)
    else:
        utc_dt = datetime.utcfromtimestamp(request_time_ms / 1000.0)
        beijing_tz = pytz.timezone('Asia/Shanghai')
        request_dt_beijing = utc_dt.replace(tzinfo=pytz.utc).astimezone(beijing_tz)

    # Define the date window: [request_dt - 4 days, request_dt + 3 days]
    min_dt = request_dt_beijing - timedelta(days=5)
    max_dt = request_dt_beijing + timedelta(days=5)

    #################################################################
    # F107
    #################################################################
    f107_data = raw_space_env_data["space_env_data"]["full_F107"]  # { "observed": {...}, "predicted": {...} }

    # Observed
    f107_obs_x = json.loads(f107_data["observed"]["xaxis"])  # e.g. ["03-11","03-12",...]
    f107_obs_vals = json.loads(f107_data["observed"]["value"])
    # Predicted
    f107_pred_x = json.loads(f107_data["predicted"]["xaxis"])
    f107_pred_vals = json.loads(f107_data["predicted"]["value"])

    # Convert to date objects
    beijing_tz = pytz.timezone('Asia/Shanghai')

    def convert_to_dateval(x_list, v_list):
        dt_list, val_list = [], []
        for date_str, val_str in zip(x_list, v_list):
            dt_utc = parse_md_to_datetime(date_str, year=request_dt_beijing.year)
            dt_utc = dt_utc.replace(tzinfo=pytz.utc)
            dt_bj = dt_utc.astimezone(beijing_tz)
            if val_str in (None, "null"):
                dt_list.append(dt_bj)
                val_list.append(None)
            else:
                dt_list.append(dt_bj)
                val_list.append(float(val_str))
        return dt_list, val_list

    f107_obs_dates, f107_obs_values = convert_to_dateval(f107_obs_x, f107_obs_vals)
    f107_pred_dates, f107_pred_values = convert_to_dateval(f107_pred_x, f107_pred_vals)

    # Filter by pivot (e.g. 03-20) or skip if you prefer?
    # We'll skip pivot logic and just label them red vs. blue for Observed vs. Predicted
    # Then filter to [min_dt, max_dt]

    obs_dates2, obs_vals2 = [], []
    for d, v in zip(f107_obs_dates, f107_obs_values):
        if v is not None and (min_dt <= d <= max_dt):
            obs_dates2.append(d)
            obs_vals2.append(v)

    pred_dates2, pred_vals2 = [], []
    for d, v in zip(f107_pred_dates, f107_pred_values):
        if v is not None and (min_dt <= d <= max_dt):
            pred_dates2.append(d)
            pred_vals2.append(v)

    # Plot F10.7
    plt.rc('font', family='SimSun')  # set font to SimSun for Chinese text
    plt.figure(figsize=(5, 3))
    ax = plt.gca()

    ax.plot(obs_dates2, obs_vals2, color='red', marker='o', markerfacecolor='white', markersize=5, label='实际')
    for x_val, y_val in zip(obs_dates2, obs_vals2):
        ax.text(x_val, y_val + 1, f"{y_val:.0f}", color='red', ha='center')

    ax.plot(pred_dates2, pred_vals2, color='blue', marker='o', markerfacecolor='white', markersize=5, label='预测')
    for x_val, y_val in zip(pred_dates2, pred_vals2):
        ax.text(x_val, y_val + 1, f"{y_val:.0f}", color='blue', ha='center')

    ax.set_title("F10.7 Index")
    ax.set_xlabel("日期")
    ax.set_ylabel("F10.7")
    ax.legend()

    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.xticks(rotation=45, ha='right')

    ax.yaxis.set_major_locator(MultipleLocator(10))
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.tick_params(which='both', direction='in')

    plt.tight_layout()
    buf_f107 = io.BytesIO()
    plt.savefig(buf_f107, format='png')
    plt.close()
    buf_f107.seek(0)

    f107_img = Image(buf_f107, width=400, height=220)
    story.append(f107_img)
    story.append(Spacer(1, 10))

    #################################################################
    # Ap
    #################################################################
    ap_data = raw_space_env_data["space_env_data"]["full_ApIndex"]  # { "observed": {...}, "predicted": {...} }

    ap_obs_x = json.loads(ap_data["observed"]["xaxis"])
    ap_obs_vals = json.loads(ap_data["observed"]["value"])
    ap_pred_x = json.loads(ap_data["predicted"]["xaxis"])
    ap_pred_vals = json.loads(ap_data["predicted"]["value"])

    ap_obs_dates, ap_obs_values = convert_to_dateval(ap_obs_x, ap_obs_vals)
    ap_pred_dates, ap_pred_values = convert_to_dateval(ap_pred_x, ap_pred_vals)

    obs_dates2_ap, obs_vals2_ap = [], []
    for d, v in zip(ap_obs_dates, ap_obs_values):
        if v is not None and (min_dt <= d <= max_dt):
            obs_dates2_ap.append(d)
            obs_vals2_ap.append(v)

    pred_dates2_ap, pred_vals2_ap = [], []
    for d, v in zip(ap_pred_dates, ap_pred_values):
        if v is not None and (min_dt <= d <= max_dt):
            pred_dates2_ap.append(d)
            pred_vals2_ap.append(v)

    plt.figure(figsize=(5, 3))
    ax2 = plt.gca()

    ax2.plot(obs_dates2_ap, obs_vals2_ap, color='red', marker='o',  markerfacecolor='white', markersize=5, label='实际')
    for x_val, y_val in zip(obs_dates2_ap, obs_vals2_ap):
        ax2.text(x_val, y_val + 1, f"{y_val:.0f}", color='red', ha='center')

    ax2.plot(pred_dates2_ap, pred_vals2_ap, color='blue', marker='o', markerfacecolor='white', markersize=5, label='预测')
    for x_val, y_val in zip(pred_dates2_ap, pred_vals2_ap):
        ax2.text(x_val, y_val + 1, f"{y_val:.0f}", color='blue', ha='center')

    ax2.set_title("Ap Index")
    ax2.set_xlabel("日期")
    ax2.set_ylabel("Ap")
    ax2.legend()

    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.xticks(rotation=45, ha='right')

    ax2.yaxis.set_major_locator(MultipleLocator(5))
    ax2.yaxis.set_minor_locator(AutoMinorLocator())
    ax2.tick_params(which='both', direction='in')

    plt.tight_layout()
    buf_ap = io.BytesIO()
    plt.savefig(buf_ap, format='png')
    plt.close()
    buf_ap.seek(0)

    ap_img = Image(buf_ap, width=400, height=220)
    story.append(ap_img)
    story.append(Spacer(1, 10))

    # --- 3rd Plot: Kp Bar Chart with 3-hour intervals ---
    kp_data_list = raw_space_env_data["space_env_data"].get("Kp_values", [])
    # Take the last 5 entries
    kp_data_last5 = kp_data_list[-5:]

    beijing_tz = pytz.timezone('Asia/Shanghai')

    def parse_kp_time_to_datetime(time_str):
        """Parses '2025-03-24 3:00' or '2025-03-24 24:00' -> Beijing tz datetime."""
        if '24:' in time_str:
            day_part = time_str.split(' ')[0]
            dt_obj = datetime.strptime(day_part, '%Y-%m-%d')
            dt_obj += timedelta(days=1)
            new_str = dt_obj.strftime('%Y-%m-%d') + ' 00:00'
            return parse_kp_time_to_datetime(new_str)
        else:
            dt_utc = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
            dt_utc = dt_utc.replace(tzinfo=pytz.utc)
            return dt_utc.astimezone(beijing_tz)

    def get_kp_color(kp_val):
        """ Returns fill color for the bar based on the Kp value. """
        if kp_val <= 3:
            return 'green'
        elif kp_val <= 5:
            return 'yellow'
        elif kp_val <= 7:
            return 'orange'
        else:
            return 'red'

    plt.figure(figsize=(5.5, 3))
    plt.rc('font', family='SimSun')  # Set Chinese font if desired

    ax3 = plt.gca()
    import matplotlib.dates as mdates

    bar_width_days = 3.0 / 24.0  # 3 hours in days (Matplotlib date units)

    x_vals, y_vals, bar_colors = [], [], []
    for entry in kp_data_last5:
        t_str = entry['time']  # '2025-03-25 3:00'
        v_str = entry['value']  # '4'
        dt_bj = parse_kp_time_to_datetime(t_str)
        kp_val = float(v_str)

        x_left = mdates.date2num(dt_bj)
        x_vals.append(x_left)
        y_vals.append(kp_val)
        bar_colors.append(get_kp_color(kp_val))

    bars = ax3.bar(
        x_vals, y_vals,
        width=bar_width_days,
        bottom=0,
        color=bar_colors,
        edgecolor='black',
        linewidth=1.5
    )

    # Label each bar
    for bar in bars:
        # bar is a Rectangle object
        height = bar.get_height()
        x_center = bar.get_x() + bar.get_width() / 2.0
        # Place label above the top
        ax3.text(x_center, height + 0.2, f"{height:.0f}", ha='center', va='bottom')

    ax3.set_title("最近12小时观测Kp值")
    ax3.set_xlabel("日期")
    ax3.set_ylabel("Kp指数")
    ax3.set_ylim(0, 9)
    ax3.set_yticks([0, 2, 4, 6, 8])

    # Format x-axis with date/time
    ax3.xaxis_date()
    ax3.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    plt.xticks(rotation=45, ha='right')

    ax3.yaxis.set_minor_locator(AutoMinorLocator())
    ax3.tick_params(which='both', direction='in')

    plt.tight_layout()
    buf_kp = io.BytesIO()
    plt.savefig(buf_kp, format='png')
    plt.close()
    buf_kp.seek(0)

    kp_img = Image(buf_kp, width=400, height=220)
    story.append(kp_img)
    story.append(Spacer(1, 20))

    # ============= End of new plots ==================

    # 新增在轨卫星轨道变化情况

    story.append(Paragraph(
        f"在轨卫星轨道变化",
        chinese_paragraph_title_style))
    story.append(Spacer(1, 10))

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

    table = Table(data, colWidths=[60, 90, 60, 60, 60, 70, 60], rowHeights=50)
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
