# DataQC API

Checks drilling data for problems and tells you what is wrong.

You send it drilling readings. It compares them against a set of rules and
reports which ones look wrong — a value out of range, a parameter sitting at
zero when it should not be, or a sudden jump in pressure.

It runs in Docker, so any computer can run it without installing Python or any
packages.

---

## 1. Start it

You only need **Docker** installed. Nothing else.

**Step 1** — create your settings file:

```bash
cp .env.example .env
```

On Windows PowerShell use `copy .env.example .env` instead.

**Step 2** — open `.env` and fill in your MySQL username, password and port.

**Step 3** — start it:

```bash
docker compose up --build
```

That's it. The API is now at **http://localhost:8000**

Open **http://localhost:8000/docs** in a browser to try it out — you can send
test requests from that page without writing any code.

To stop it, press `Ctrl+C`, or run `docker compose down`.

---

## 2. The two ways to use it

### Realtime — check one reading at a time

Use this while drilling. Send one reading, get the problems back immediately.

`POST http://localhost:8000/DataQC_real`

```bash
curl -X POST http://localhost:8000/DataQC_real \
  -H "Content-Type: application/json" \
  -d '{
    "Activity": "Drilling", "depth": 1035.0,
    "ROP": 12.0, "Hookload": 150.0, "WOB": 0.0,
    "TotalRPM": 60.0, "TotalSPM": 90.0, "SPP": 2500.0,
    "TG": 10.0, "TA": 5.0, "MW_IN": 9.5, "MW_Out": 9.6,
    "Temp_In": 40.0, "Temp_Out": 45.0,
    "H2S": 10.0, "LEL": 2.0, "Co2": 0.1
  }'
```

You get back:

```json
{
  "status": "success",
  "alerts": [
    "[30-08-26 13-53-24] WOB cannot be 0 in Drilling where bed is1035.0"
  ]
}
```

An empty `alerts` list means the reading passed every check.

Every reading you send is also saved to a spreadsheet — see section 5.

### Offline — check a whole batch from the database

Use this to review data afterwards. It pulls rows from MySQL and checks them
all at once.

`POST http://localhost:8000/DataQC_offline`

```bash
curl -X POST http://localhost:8000/DataQC_offline \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.138",
    "database_name": "lkbl-1-wc",
    "table_name": "drilling",
    "start_depth": 300,
    "end_depth": 1035
  }'
```

You can filter by depth (`start_depth` / `end_depth`), by time
(`start_date` / `end_date`), or both together. Leave all four out and it reads
the whole table.

---

## 3. What it actually checks

There are six checks. All of them are controlled by the JSON files in the
`data/` folder, so you can change the limits without touching any code.

| # | Check | What it catches | Set in |
|---|---|---|---|
| 1 | **Activity** | A parameter is 0 when that activity requires it (e.g. WOB is 0 while Drilling) | `data/activity.json` |
| 2 | **Range** | A value is below the minimum or above the maximum (e.g. H2S above 50 ppm) | `data/ranges.json` |
| 3 | **TA > TG** | Gas TA stays above TG for 90 seconds | `data/conditions.json` |
| 4 | **SPP change** | Standpipe pressure jumps or drops by more than 1% | `data/conditions.json` |
| 5 | **TotalSPM change** | Pump strokes jump or drop by more than 1% | `data/conditions.json` |
| 6 | **ROP change** | Rate of penetration increases by more than 20% | `data/conditions.json` |

### Changing the limits

Open the file, edit the number, then restart:

```bash
docker compose restart
```

No rebuild is needed — the `data/` folder is shared with the container.

**`data/ranges.json`** — the allowed range for each parameter:

```json
"H2S": { "min": 0, "max": 50, "unit": "ppm" }
```

**`data/activity.json`** — which parameters may not be zero. `1` means
required, `0` means ignore it:

```json
"Drilling": { "ROP": 1, "Hookload": 1, "WOB": 1, "TG": 0 }
```

Activities defined: `Drilling`, `POOH`, `RIH`, `Pipe Connection`, `Sliding`.

**`data/conditions.json`** — how big a change must be, and over how long,
before it counts:

```json
"SPP": { "percentage_change": 1, "duration_seconds": 5 }
```

### How the change checks work (checks 4, 5 and 6)

These compare each reading against an earlier one, so they need two readings
before they can say anything:

1. The first reading is remembered as the starting point.
2. When a later reading arrives **and** enough seconds have passed
   (`duration_seconds`), it works out the percentage change.
3. If the change is bigger than `percentage_change`, you get an alert.
4. That reading then becomes the new starting point.

Because of step 1, the very first reading after startup never raises a change
alert. That is expected.

---

## 4. Reading the terminal output

When it starts, it prints what it is using, so a wrong setting is obvious
straight away:

```
13:53:23 | INFO  | startup   | +--------------------------------------------------+
13:53:23 | INFO  | startup   | | DataQC API                                       |
13:53:23 | INFO  | startup   | |                                                  |
13:53:23 | INFO  | startup   | | Listening   : http://0.0.0.0:8000                |
13:53:23 | INFO  | startup   | | Swagger UI  : http://0.0.0.0:8000/docs           |
13:53:23 | INFO  | startup   | | Log level   : INFO                               |
13:53:23 | INFO  | startup   | | Logs        : terminal only, not written to disk |
13:53:23 | INFO  | startup   | | Working dir : /app                               |
13:53:23 | INFO  | startup   | +--------------------------------------------------+
13:53:23 | INFO  | api       | Database credentials loaded (user=root, port=3306)
13:53:23 | INFO  | api       | Startup complete, waiting for requests
```

Then every request shows up as it arrives and again when it finishes, with any
alerts listed in between:

```
13:53:24 | INFO  | api       | --> POST /DataQC_real
13:53:24 | INFO  | api       | Reading received: activity=Drilling depth=1035.0 SPP=2500.0 TotalSPM=90.0 ROP=12.0
13:53:24 | WARN  | api       | 1 alert(s) raised:
13:53:24 | WARN  | api       |    [30-08-26 13-53-24] WOB cannot be 0 in Drilling where bed is1035.0
13:53:24 | INFO  | api       | <-- POST /DataQC_real  200  19.6ms
```

Each line reads as `time | level | source | message`:

- `-->` means a request came in, `<--` means it finished.
- The number after `<--` is the HTTP status (`200` is success) and how long it
  took.
- `INFO` is green and normal. `WARN` is yellow and means an alert was raised.
  `ERROR` is red and means something broke.

For more detail, including the SQL query the offline endpoint builds, set
`LOG_LEVEL=DEBUG` in `.env` and restart.

**No log files are created.** Logs go to the terminal only. If you started it
in the background with `-d`, view them with:

```bash
docker compose logs -f
```

---

## 5. Where your results are saved

Every realtime reading is added to a spreadsheet in the `output/` folder, one
file per day:

```
output/30-08-26_data.csv
```

It contains the values you sent, the percentage changes that were calculated,
and any alerts raised. Open it in Excel.

This folder is on your computer, not inside the container, so the files stay
there when you stop or rebuild.

---

## 6. Settings

Everything lives in `.env`. After changing anything run
`docker compose restart` — you never need to rebuild.

| Setting | Example | What it does |
|---|---|---|
| `DB_USERNAME` | `root` | MySQL username, for the offline endpoint |
| `DB_PASSWORD` | `secret` | MySQL password |
| `DB_PORT` | `3306` | MySQL port |
| `TZ` | `Asia/Kolkata` | Your timezone. **Set this** — otherwise times show as UTC |
| `LOG_LEVEL` | `INFO` | Use `DEBUG` to see more detail |
| `LOG_COLOR` | `auto` | `never` turns colour off |
| `HOST` | `0.0.0.0` | Leave as-is |
| `PORT` | `8000` | Leave as-is |

There is no database host or table name here on purpose. Those are sent with
each offline request instead, so one running service can check several rigs.

### Using a different port

If port 8000 is already taken, edit `docker-compose.yml` and change only the
**left** number:

```yaml
ports:
  - "9000:8000"     # now use http://localhost:9000
```

---

## 7. If something goes wrong

**"port is already allocated"**
Something else is using port 8000. Change it as shown above.

**The offline endpoint cannot connect to the database**
The `ip` you send must be reachable *from inside the container*. If MySQL runs
on the same computer as Docker, use `host.docker.internal` instead of
`localhost` or `127.0.0.1`.

**Timestamps are several hours off**
`TZ` is not set in `.env`. Containers default to UTC.

**Unexpected alerts, or none when you expected some**
Check the limits in `data/`. Remember checks 4–6 need at least two readings
spaced `duration_seconds` apart before they report anything.

**Changed a file but nothing happened**
Changes to `data/*.json` and `.env` need `docker compose restart`.
Changes to `.py` files need `docker compose up --build`.

---

## 8. Running without Docker

Only if you already have Python 3.12 and [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run python main.py
```

---

## 9. Project files

```
main.py                  the API: endpoints, request logging, startup
logger.py                terminal log formatting and colours
validation_realtime.py   the six checks, for one live reading
validation_offline.py    the same checks, for a batch from MySQL
save_excel.py            writes each realtime reading to the daily CSV
data/                    the rule files you can edit
Dockerfile               how the image is built
docker-compose.yml       how the container is run
.env                     your settings (never committed, never in the image)
```

---

## Two things worth knowing

**It runs one worker on purpose.** Checks 4–6 remember the previous reading in
memory. If several workers ran at once, each would keep its own memory and the
percentage checks would give wrong answers.

**Your credentials stay out of the image.** `.env` is excluded by
`.dockerignore` and `.gitignore`, so it is never built into the image or
committed to git. The container also runs as a normal user, not root.
