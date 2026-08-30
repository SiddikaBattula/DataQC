import json

with open("data/ranges.json", "r") as f:
    RANGES = json.load(f)
with open("data/activity.json", "r") as f:
    ACTIVITY_RULES = json.load(f)
with open("data/conditions.json", "r") as f:
    VALIDATION_CONFIG = json.load(f)


ta_tg_duration = VALIDATION_CONFIG["TA_TG"]["duration_seconds"]

spp_threshold = VALIDATION_CONFIG["SPP"]["percentage_change"]
spp_duration = VALIDATION_CONFIG["SPP"]["duration_seconds"]

totalspm_threshold = VALIDATION_CONFIG["TotalSPM"]["percentage_change"]
totalspm_duration = VALIDATION_CONFIG["TotalSPM"]["duration_seconds"]

rop_threshold = VALIDATION_CONFIG["ROP"]["percentage_change"]
rop_duration = VALIDATION_CONFIG["ROP"]["duration_seconds"]


def generate_notification_report(data):

    alerts = []

    previous_spp = None
    previous_totalspm = None
    previous_rop = None

    ta_tg_start_time = None

    for row in data:

        depth = row.get("DMEA")
        timestamp = str(row.get("TIME"))

        # ==================================================
        # RANGE VALIDATION
        # ==================================================
        for param, limits in RANGES.items():

            value = row.get(param)

            if value is None:
                continue

            min_val = limits["min"]
            max_val = limits["max"]
            unit = limits.get("unit", "")

            if value < min_val:
                alerts.append({
                    "TIME": timestamp,
                    "DEPTH": depth,
                    "ALERT_TYPE": "RANGE",
                    "PARAMETER": param,
                    "MESSAGE": f"{param}={value}{unit} below minimum limit {min_val}{unit}"
                })

            elif value > max_val:
                alerts.append({
                    "TIME": timestamp,
                    "DEPTH": depth,
                    "ALERT_TYPE": "RANGE",
                    "PARAMETER": param,
                    "MESSAGE": f"{param}={value}{unit} above maximum limit {max_val}{unit}"
                })

        # ==================================================
        # ACTIVITY VALIDATION
        # ==================================================
        # activity = row.get("Activity")

        # if activity:

        #     rules = ACTIVITY_RULES.get(activity, {})

        #     for param, mandatory in rules.items():

        #         if mandatory == 1:

        #             value = row.get(param)

        #             if value is None or value <= 0:

        #                 alerts.append({
        #                     "TIME": timestamp,
        #                     "DEPTH": depth,
        #                     "ALERT_TYPE": "ACTIVITY",
        #                     "PARAMETER": param,
        #                     "MESSAGE": f"{param} cannot be 0 during {activity}"
        #                 })

        # ==================================================
        # TA > TG VALIDATION
        # ==================================================
        ta = row.get("TA")
        tg = row.get("TG")

        if ta is not None and tg is not None:

            if ta > tg:

                if ta_tg_start_time is None:
                    ta_tg_start_time = row.get("TIME")

                elapsed = (
                    row.get("TIME") - ta_tg_start_time
                ).total_seconds()

                if elapsed >= ta_tg_duration:

                    alerts.append({
                        "TIME": timestamp,
                        "DEPTH": depth,
                        "ALERT_TYPE": "TA_TG",
                        "PARAMETER": "TA",
                        "MESSAGE": f"TA ({ta}) is greater than TG ({tg}) for {elapsed:.0f} sec"
                    })

            else:
                ta_tg_start_time = None

        # ==================================================
        # SPP VALIDATION
        # ==================================================
        spp = row.get("SPP")

        if spp is not None:

            if previous_spp is not None and previous_spp > 0:

                percent_change = (
                    (spp - previous_spp)
                    / previous_spp
                ) * 100

                if abs(percent_change) >= spp_threshold:

                    alerts.append({
                        "TIME": timestamp,
                        "DEPTH": depth,
                        "ALERT_TYPE": "SPP",
                        "PARAMETER": "SPP",
                        "MESSAGE": f"SPP changed by {percent_change:.2f}%"
                    })

            previous_spp = spp

        # ==================================================
        # TOTALSPM VALIDATION
        # ==================================================
        totalspm = row.get("TotalSPM")

        if totalspm is not None:

            if previous_totalspm is not None and previous_totalspm > 0:

                percent_change = (
                    (totalspm - previous_totalspm)
                    / previous_totalspm
                ) * 100

                if abs(percent_change) >= totalspm_threshold:

                    alerts.append({
                        "TIME": timestamp,
                        "DEPTH": depth,
                        "ALERT_TYPE": "TotalSPM",
                        "PARAMETER": "TotalSPM",
                        "MESSAGE": f"TotalSPM changed by {percent_change:.2f}%"
                    })

            previous_totalspm = totalspm

        # ==================================================
        # ROP VALIDATION
        # ==================================================
        rop = row.get("ROP")

        if rop is not None:

            if previous_rop is not None and previous_rop > 0:

                percent_change = (
                    (rop - previous_rop)
                    / previous_rop
                ) * 100

                if percent_change >= rop_threshold:

                    alerts.append({
                        "TIME": timestamp,
                        "DEPTH": depth,
                        "ALERT_TYPE": "ROP",
                        "PARAMETER": "ROP",
                        "MESSAGE": f"ROP increased by {percent_change:.2f}%"
                    })

            previous_rop = rop

    return alerts

























# import json

# with open("data/ranges.json", "r") as f:
#     RANGES = json.load(f)

# with open("data/activity.json", "r") as f:
#     ACTIVITY_RULES = json.load(f)

# with open("data/conditions.json", "r") as f:
#     VALIDATION_CONFIG = json.load(f)



# ta_tg_duration = VALIDATION_CONFIG["TA_TG"]["duration_seconds"]

# spp_threshold = VALIDATION_CONFIG["SPP"]["percentage_change"]
# spp_duration = VALIDATION_CONFIG["SPP"]["duration_seconds"]

# totalspm_threshold = VALIDATION_CONFIG["TotalSPM"]["percentage_change"]
# totalspm_duration = VALIDATION_CONFIG["TotalSPM"]["duration_seconds"]

# rop_threshold = VALIDATION_CONFIG["ROP"]["percentage_change"]
# rop_duration = VALIDATION_CONFIG["ROP"]["duration_seconds"]


# from datetime import datetime

def get_alert_prefix_suffix(data):
    date_str = datetime.now().strftime("%d-%m-%y %H-%M-%S")
    depth = data.get("depth")
    return date_str, depth

def validate_activity_conditions(data: dict):
    alerts = []

    activity = data.get("Activity")

    if not activity:
        return ["Activity is missing"]

    rules = ACTIVITY_RULES.get(activity)

    if not rules:
        return [f"Unknown activity: {activity}"]

    for param, is_mandatory in rules.items():

        value = data.get(param)

        # Rule = 1 means value must be > 0
        if is_mandatory == 1:

            date_str, depth = get_alert_prefix_suffix(data)
            if value is None or value <= 0:
                alerts.append(
                    f"[{date_str}] {param} cannot be 0 in {activity} where bed is{depth}"
                )

    return alerts



def validate_ranges(data: dict):
    alerts = []

    for param, limits in RANGES.items():
        value = data.get(param)

        if value is None:
            continue
    
        min_val = limits["min"]
        max_val = limits["max"]
        unit = limits.get("unit", "")

        date_str, depth = get_alert_prefix_suffix(data)
        if value < min_val:
            alerts.append(
                f"[{date_str}] {param} - {value} {unit} is below minimum limit {min_val}{unit} BD-{depth}"
            )

        elif value > max_val:
            alerts.append(
                f"[{date_str}] {param} - {value} {unit} is above maximum limit {max_val}{unit}  BD-{depth}"
            )

    return alerts







from datetime import datetime

ta_gt_tg_start = None


def validate_ta_tg(data):
    global ta_gt_tg_start

    alerts = []

    ta = data.get("TA")
    tg = data.get("TG")

    if ta is None or tg is None:
        return alerts

    if ta > tg:
        if ta_gt_tg_start is None:
            ta_gt_tg_start = datetime.now()

        elapsed = (datetime.now() - ta_gt_tg_start).total_seconds()

        date_str, depth = get_alert_prefix_suffix(data)
        if elapsed >= ta_tg_duration:
            alerts.append(f"[{date_str}] TA is greater than TG where BD-{depth}")
    else:
        # Reset timer when condition clears
        ta_gt_tg_start = None

    return alerts




from datetime import datetime

previous_spp = None
previous_spp_time = None


def validate_spp_change(data):
    global previous_spp, previous_spp_time

    alerts = []

    spp = data.get("SPP")

    if spp is None:
        return alerts, 0.0

    current_time = datetime.now()

    # First value
    if previous_spp is None:
        previous_spp = spp
        previous_spp_time = current_time
        return alerts, 0.0

    # Prevent division by zero
    if previous_spp <= 0:
        previous_spp = spp
        previous_spp_time = current_time
        return alerts, 0.0

    elapsed = (
        current_time - previous_spp_time
    ).total_seconds()

    if elapsed >= spp_duration:

        percent_change = (
            (spp - previous_spp) / previous_spp
        ) * 100

        date_str, depth = get_alert_prefix_suffix(data)

        if percent_change > spp_threshold:
            alerts.append(
                f"[{date_str}] SPP increased by {percent_change:.2f}% where BD-{depth}"
            )

        elif percent_change < -spp_threshold:
            alerts.append(
                f"[{date_str}] SPP dropped by {abs(percent_change):.2f}% where BD-{depth}"
            )

        # Reset baseline
        previous_spp = spp
        previous_spp_time = current_time

        return alerts, round(percent_change, 2)

    return alerts, 0.0




from datetime import datetime

previous_totalspm = None
previous_totalspm_time = None


def validate_totalspm_change(data):
    global previous_totalspm, previous_totalspm_time

    alerts = []

    totalspm = data.get("TotalSPM")

    if totalspm is None:
        return alerts, 0.0

    current_time = datetime.now()

    # First value
    if previous_totalspm is None:
        previous_totalspm = totalspm
        previous_totalspm_time = current_time
        return alerts, 0.0

    # Prevent division by zero
    if previous_totalspm <= 0:
        previous_totalspm = totalspm
        previous_totalspm_time = current_time
        return alerts, 0.0

    elapsed = (
        current_time - previous_totalspm_time
    ).total_seconds()

    if elapsed >= totalspm_duration:

        percent_change = (
            (totalspm - previous_totalspm)
            / previous_totalspm
        ) * 100

        date_str, depth = get_alert_prefix_suffix(data)

        if percent_change > totalspm_threshold:
            alerts.append(
                f"[{date_str}] TotalSPM increased by {percent_change:.2f}% Where BD-{depth}"
            )

        elif percent_change < -totalspm_threshold:
            alerts.append(
                f"[{date_str}] TotalSPM dropped by {abs(percent_change):.2f}% Where BD-{depth}"
            )

        previous_totalspm = totalspm
        previous_totalspm_time = current_time

        return alerts, round(percent_change, 2)

    return alerts, 0.0






from datetime import datetime

previous_rop = None
previous_rop_time = None


def validate_rop_change(data):
    global previous_rop, previous_rop_time

    alerts = []

    rop = data.get("ROP")

    if rop is None:
        return alerts, 0.0

    current_time = datetime.now()

    if previous_rop is None:
        previous_rop = rop
        previous_rop_time = current_time
        return alerts, 0.0


    elapsed = (
        current_time - previous_rop_time
    ).total_seconds()

    if elapsed >= rop_duration:

        percent_change = (
            (rop - previous_rop)
            / previous_rop
        ) * 100

        date_str, depth = get_alert_prefix_suffix(data)

        if percent_change > rop_threshold:
            alerts.append(
                f"[{date_str}] ROP increased by {percent_change:.2f}% Where BD-{depth}"
            )

        previous_rop = rop
        previous_rop_time = current_time

        return alerts, round(percent_change, 2)

    return alerts, 0.0



