# ---------------------------------------------------------------------------
# Persistent state (kept across realtime calls) — same globals as before
# ---------------------------------------------------------------------------


import json
from datetime import datetime


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


ta_gt_tg_start = None

previous_spp = None
previous_spp_time = None

previous_totalspm = None
previous_totalspm_time = None

previous_rop = None
previous_rop_time = None


def validate_realtime_data(data: dict):
    """
    Runs every realtime QC check in one place.
    Returns: (alerts, spp_percentage, totalspm_percentage, rop_percentage)
    Alert strings are kept exactly as in the original functions.
    """
    global ta_gt_tg_start
    global previous_spp, previous_spp_time
    global previous_totalspm, previous_totalspm_time
    global previous_rop, previous_rop_time

    alerts = []

    date_str = datetime.now().strftime("%d-%m-%y %H-%M-%S")
    depth = data.get("depth")

    spp_percentage = 0.0
    totalspm_percentage = 0.0
    rop_percentage = 0.0

    # ------------------------------------------------------------------
    # 1. Activity conditions
    # ------------------------------------------------------------------
    activity = data.get("Activity")

    if not activity:
        alerts.append("Activity is missing")

    else:
        rules = ACTIVITY_RULES.get(activity)

        if not rules:
            alerts.append(f"Unknown activity: {activity}")

        else:
            for param, is_mandatory in rules.items():

                value = data.get(param)

                # Rule = 1 means value must be > 0
                if is_mandatory == 1:
                    if value is None or value <= 0:
                        alerts.append(
                            f"[{date_str}] {param} cannot be 0 in {activity} where bed is{depth}"
                        )

    # ------------------------------------------------------------------
    # 2. Ranges
    # ------------------------------------------------------------------
    for param, limits in RANGES.items():
        value = data.get(param)

        if value is None:
            continue

        min_val = limits["min"]
        max_val = limits["max"]
        unit = limits.get("unit", "")

        if value < min_val:
            alerts.append(
                f"[{date_str}] {param} - {value} {unit} is below minimum limit {min_val}{unit} BD-{depth}"
            )

        elif value > max_val:
            alerts.append(
                f"[{date_str}] {param} - {value} {unit} is above maximum limit {max_val}{unit}  BD-{depth}"
            )

    # ------------------------------------------------------------------
    # 3. TA > TG
    # ------------------------------------------------------------------
    ta = data.get("TA")
    tg = data.get("TG")

    if ta is not None and tg is not None:
        if ta > tg:
            if ta_gt_tg_start is None:
                ta_gt_tg_start = datetime.now()

            elapsed = (datetime.now() - ta_gt_tg_start).total_seconds()

            if elapsed >= ta_tg_duration:
                alerts.append(f"[{date_str}] TA is greater than TG where BD-{depth}")
        else:
            # Reset timer when condition clears
            ta_gt_tg_start = None

    # ------------------------------------------------------------------
    # 4. SPP change
    # ------------------------------------------------------------------
    spp = data.get("SPP")

    if spp is not None and spp>0:
        current_time = datetime.now()

        # First value
        if previous_spp is None:
            previous_spp = spp
            previous_spp_time = current_time

        # Prevent division by zero
        elif previous_spp <= 0:
            previous_spp = spp
            previous_spp_time = current_time

        else:
            elapsed = (current_time - previous_spp_time).total_seconds()

            if elapsed >= spp_duration:

                percent_change = ((spp - previous_spp) / previous_spp) * 100

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

                spp_percentage = round(percent_change, 2)

    # ------------------------------------------------------------------
    # 5. TotalSPM change
    # ------------------------------------------------------------------
    totalspm = data.get("TotalSPM")

    if totalspm is not None:
        current_time = datetime.now()

        # First value
        if previous_totalspm is None:
            previous_totalspm = totalspm
            previous_totalspm_time = current_time

        # Prevent division by zero
        elif previous_totalspm <= 0:
            previous_totalspm = totalspm
            previous_totalspm_time = current_time

        else:
            elapsed = (current_time - previous_totalspm_time).total_seconds()

            if elapsed >= totalspm_duration:

                percent_change = (
                    (totalspm - previous_totalspm) / previous_totalspm
                ) * 100

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

                totalspm_percentage = round(percent_change, 2)

    # ------------------------------------------------------------------
    # 6. ROP change
    # ------------------------------------------------------------------
    rop = data.get("ROP")

    if rop is not None:
        current_time = datetime.now()

        # First value
        if previous_rop is None:
            previous_rop = rop
            previous_rop_time = current_time

        # Prevent division by zero. ROP is legitimately 0 whenever the bit is
        # not advancing (tripping, connections, circulating), so without this
        # the next reading would divide by a zero baseline.
        elif previous_rop <= 0:
            previous_rop = rop
            previous_rop_time = current_time

        else:
            elapsed = (current_time - previous_rop_time).total_seconds()

            if elapsed >= rop_duration:

                percent_change = ((rop - previous_rop) / previous_rop) * 100

                if percent_change > rop_threshold:
                    alerts.append(
                        f"[{date_str}] ROP increased by {percent_change:.2f}% Where BD-{depth}"
                    )

                previous_rop = rop
                previous_rop_time = current_time

                rop_percentage = round(percent_change, 2)

    return alerts, spp_percentage, totalspm_percentage, rop_percentage
