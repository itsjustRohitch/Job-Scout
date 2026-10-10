from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import db

app = FastAPI(title="JobScout Mission Control")

@app.get("/api/jobs")
def get_jobs(status: str = "all"):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if status == "all":
            cursor.execute("SELECT * FROM jobs ORDER BY match_score DESC, created_at DESC LIMIT 100;")
        else:
            cursor.execute("SELECT * FROM jobs WHERE application_status = ? ORDER BY match_score DESC, created_at DESC LIMIT 100;", (status,))
        return [dict(row) for row in cursor.fetchall()]

@app.post("/api/jobs/{job_id}/status")
def update_status(job_id: str, new_status: str):
    success = db.update_job_status(job_id, new_status)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "updated", "job_id": job_id, "new_status": new_status}

@app.get("/api/stats")
def get_stats():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs;")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM jobs WHERE match_score >= 60;")
        matches = cursor.fetchone()[0]

        cursor.execute("SELECT application_status, COUNT(*) FROM jobs GROUP BY application_status;")
        breakdown = dict(cursor.fetchall())

        cursor.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source;")
        sources = dict(cursor.fetchall())

    return {
        "total": total,
        "matches": matches,
        "breakdown": breakdown,
        "sources": sources
    }

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>JobScout Agent | Control Deck</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            charcoal: {
              950: '#090a0c', // deep canvas matte black
              900: '#121316', // elevated card surface
              800: '#1b1d22', // secondary surfaces / pill bg
              700: '#282b32', // subtle borders
              600: '#3e424d'
            }
          }
        }
      }
    }
  </script>
</head>
<body class="bg-charcoal-950 text-neutral-200 min-h-screen p-6 md:p-10 font-sans antialiased selection:bg-neutral-800 selection:text-white">
  <div class="max-w-7xl mx-auto space-y-8">
    <!-- Header -->
    <header class="flex flex-col md:flex-row justify-between items-start md:items-center pb-6 border-b border-charcoal-700/60 gap-4">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-neutral-100 flex items-center gap-2.5">
          <span class="text-amber-500">⚡</span>
          <span>JobScout Mission Control</span>
        </h1>
        <p class="text-neutral-500 text-xs font-mono tracking-wide mt-1">AUTONOMOUS MULTI-STREAM INGESTION &bull; LOCAL LLM ENGINE</p>
      </div>
      <div id="stats-bar" class="flex flex-wrap gap-3"></div>
    </header>

    <!-- Filter Pills -->
    <div class="flex items-center gap-3">
      <span class="text-[11px] font-mono uppercase tracking-wider text-neutral-500">Status:</span>
      <div class="flex flex-wrap gap-2" id="filter-buttons">
        <button onclick="loadJobs('all')" class="filter-btn px-3 py-1 rounded-md text-xs font-medium bg-charcoal-700 text-neutral-100 border border-charcoal-600">All</button>
        <button onclick="loadJobs('pending')" class="filter-btn px-3 py-1 rounded-md text-xs font-medium bg-charcoal-900 text-neutral-400 border border-charcoal-700/50 hover:border-charcoal-600">Pending</button>
        <button onclick="loadJobs('saved')" class="filter-btn px-3 py-1 rounded-md text-xs font-medium bg-charcoal-900 text-amber-400/90 border border-charcoal-700/50 hover:border-charcoal-600">Saved</button>
        <button onclick="loadJobs('applied')" class="filter-btn px-3 py-1 rounded-md text-xs font-medium bg-charcoal-900 text-emerald-400/90 border border-charcoal-700/50 hover:border-charcoal-600">Applied</button>
        <button onclick="loadJobs('pass')" class="filter-btn px-3 py-1 rounded-md text-xs font-medium bg-charcoal-900 text-neutral-500 border border-charcoal-700/50 hover:border-charcoal-600">Passed</button>
      </div>
    </div>

    <!-- Job Cards Grid -->
    <main id="job-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"></main>
  </div>

  <script>
    let activeFilter = 'all';

    async function fetchStats() {
      const res = await fetch('/api/stats');
      const data = await res.json();
      const b = data.breakdown || {};
      document.getElementById('stats-bar').innerHTML = `
        <div class="bg-charcoal-900 px-3.5 py-1.5 rounded-lg border border-charcoal-700/50 text-right">
          <span class="text-[10px] uppercase font-mono tracking-wider text-neutral-500 block">Ingested</span>
          <p class="text-base font-semibold text-neutral-200">${data.total}</p>
        </div>
        <div class="bg-charcoal-900 px-3.5 py-1.5 rounded-lg border border-charcoal-700/50 text-right">
          <span class="text-[10px] uppercase font-mono tracking-wider text-neutral-500 block">Matches (&ge;60)</span>
          <p class="text-base font-semibold text-indigo-400">${data.matches}</p>
        </div>
        <div class="bg-charcoal-900 px-3.5 py-1.5 rounded-lg border border-charcoal-700/50 text-right">
          <span class="text-[10px] uppercase font-mono tracking-wider text-neutral-500 block">Applied</span>
          <p class="text-base font-semibold text-emerald-400">${b.applied || 0}</p>
        </div>
        <div class="bg-charcoal-900 px-3.5 py-1.5 rounded-lg border border-charcoal-700/50 text-right">
          <span class="text-[10px] uppercase font-mono tracking-wider text-neutral-500 block">Saved</span>
          <p class="text-base font-semibold text-amber-400">${b.saved || 0}</p>
        </div>
      `;
    }

    async function loadJobs(status = 'all') {
      activeFilter = status;
      const res = await fetch(`/api/jobs?status=${status}`);
      const jobs = await res.json();
      const grid = document.getElementById('job-grid');
      
      if (jobs.length === 0) {
        grid.innerHTML = '<div class="col-span-full py-20 text-center font-mono text-xs text-neutral-600">No jobs matching current filter.</div>';
        return;
      }

      grid.innerHTML = jobs.map(j => `
        <div class="bg-charcoal-900 border border-charcoal-700/60 rounded-xl p-5 flex flex-col justify-between hover:border-charcoal-600 transition-colors shadow-sm">
          <div class="space-y-3">
            <div class="flex justify-between items-center">
              <span class="text-[11px] font-mono px-2 py-0.5 rounded-md font-medium ${
                j.match_score >= 80 ? 'bg-emerald-950/70 text-emerald-400 border border-emerald-800/60' :
                j.match_score >= 60 ? 'bg-indigo-950/70 text-indigo-300 border border-indigo-800/60' :
                'bg-charcoal-800 text-neutral-400 border border-charcoal-700'
              }">Score: ${j.match_score}</span>
              <span class="text-[10px] font-mono text-neutral-500 uppercase tracking-wider">${j.source || 'web'}</span>
            </div>

            <div>
              <h2 class="font-semibold text-base text-neutral-100 leading-snug line-clamp-2">${j.position}</h2>
              <p class="text-xs text-neutral-400 mt-1">${j.company} &bull; <span class="text-neutral-500">${j.location}</span></p>
            </div>

            <p class="text-xs text-neutral-400/90 line-clamp-3 leading-relaxed font-normal">${j.description || ''}</p>
          </div>

          <div class="mt-5 pt-3.5 border-t border-charcoal-800 flex items-center justify-between">
            <a href="${j.url}" target="_blank" class="text-xs font-mono text-indigo-400 hover:text-indigo-300 transition-colors">
              Open Link &rarr;
            </a>
            <div class="flex gap-1.5">
              <button onclick="setStatus('${j.id}', 'saved')" class="text-xs font-mono px-2.5 py-1 rounded bg-charcoal-800 hover:bg-charcoal-700 text-amber-300/90 border border-charcoal-700">Save</button>
              <button onclick="setStatus('${j.id}', 'applied')" class="text-xs font-mono px-2.5 py-1 rounded bg-charcoal-800 hover:bg-charcoal-700 text-emerald-400/90 border border-charcoal-700">Apply</button>
              <button onclick="setStatus('${j.id}', 'pass')" class="text-xs font-mono px-2.5 py-1 rounded bg-charcoal-800 hover:bg-charcoal-700 text-neutral-400 border border-charcoal-700">Pass</button>
            </div>
          </div>
        </div>
      `).join('');
    }

    async function setStatus(jobId, status) {
      await fetch(`/api/jobs/${jobId}/status?new_status=${status}`, { method: 'POST' });
      fetchStats();
      loadJobs(activeFilter);
    }

    fetchStats();
    loadJobs('all');
  </script>
</body>
</html>
    """
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard:app", host="127.0.0.1", port=8000, reload=True)