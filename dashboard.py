from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import db

app = FastAPI(title="JobScout Mission Control")


class CustomJobInput(BaseModel):
    position: str
    company: str
    url: str
    location: Optional[str] = "Remote"
    description: Optional[str] = ""


@app.get("/api/jobs")
def get_jobs(status: str = "all"):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if status == "all":
            cursor.execute(
                "SELECT * FROM jobs ORDER BY match_score DESC, created_at DESC LIMIT 150;"
            )
        else:
            cursor.execute(
                "SELECT * FROM jobs WHERE application_status = ? ORDER BY match_score DESC, created_at DESC LIMIT 150;",
                (status,),
            )
        return [dict(row) for row in cursor.fetchall()]


@app.post("/api/jobs/{job_id}/status")
def update_status(job_id: str, new_status: str):
    success = db.update_job_status(job_id, new_status)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "updated", "job_id": job_id, "new_status": new_status}


@app.delete("/api/jobs/{job_id}")
def delete_job_record(job_id: str):
    success = db.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "deleted", "job_id": job_id}


@app.post("/api/jobs/manual")
def create_manual_job(data: CustomJobInput):
    job_id = db.add_custom_job(
        position=data.position,
        company=data.company,
        url=data.url,
        location=data.location or "Remote",
        description=data.description or "",
    )
    return {"status": "created", "job_id": job_id}


@app.post("/api/maintenance/prune")
def run_prune():
    stats = db.prune_duplicates_and_stale()
    return stats


@app.get("/api/stats")
def get_stats():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs;")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM jobs WHERE match_score >= 60;")
        matches = cursor.fetchone()[0]

        cursor.execute(
            "SELECT application_status, COUNT(*) FROM jobs GROUP BY application_status;"
        )
        breakdown = dict(cursor.fetchall())

        cursor.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source;")
        sources = dict(cursor.fetchall())

    return {
        "total": total,
        "matches": matches,
        "breakdown": breakdown,
        "sources": sources,
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
              950: '#090a0c',
              900: '#121316',
              800: '#1b1d22',
              700: '#282b32',
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
        <p class="text-neutral-500 text-xs font-mono tracking-wide mt-1">AUTONOMOUS MULTI-STREAM INGESTION &bull; TIMELINE MANAGEMENT</p>
      </div>

      <div class="flex items-center gap-4">
        <div id="stats-bar" class="flex flex-wrap gap-2.5"></div>
        <div class="flex gap-2">
          <button onclick="openModal()" class="px-3 py-1.5 rounded-lg text-xs font-mono bg-charcoal-800 hover:bg-charcoal-700 text-neutral-200 border border-charcoal-700 transition">
            ➕ Add Job
          </button>
          <button onclick="pruneDatabase()" class="px-3 py-1.5 rounded-lg text-xs font-mono bg-charcoal-800 hover:bg-rose-950/40 text-neutral-300 border border-charcoal-700 transition" title="Removes duplicate postings across scrapers">
            🧹 Prune Dupes
          </button>
          <button onclick="purgeJunk()" class="px-3 py-1.5 rounded-lg text-xs font-mono bg-charcoal-800 hover:bg-rose-950/40 text-rose-300 border border-charcoal-700 transition" title="Purges <50% score and foreign-language postings">
            🗑️ Purge < 50%
          </button>
        </div>
      </div>
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

  <!-- Manual Add Job Modal -->
  <div id="add-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm hidden items-center justify-center p-4 z-50">
    <div class="bg-charcoal-900 border border-charcoal-700 rounded-xl p-6 w-full max-w-md space-y-4 shadow-xl">
      <div class="flex justify-between items-center">
        <h3 class="font-bold text-sm text-neutral-100">Add External / Referral Job</h3>
        <button onclick="closeModal()" class="text-neutral-500 hover:text-neutral-300 font-mono text-sm">&times;</button>
      </div>
      <div class="space-y-3 text-xs">
        <div>
          <label class="text-neutral-400 block mb-1">Position Title *</label>
          <input id="new-pos" class="w-full bg-charcoal-950 border border-charcoal-700 rounded px-3 py-2 text-neutral-200 outline-none focus:border-neutral-500" placeholder="e.g. Backend Engineering Intern" />
        </div>
        <div>
          <label class="text-neutral-400 block mb-1">Company *</label>
          <input id="new-comp" class="w-full bg-charcoal-950 border border-charcoal-700 rounded px-3 py-2 text-neutral-200 outline-none focus:border-neutral-500" placeholder="e.g. Stripe" />
        </div>
        <div>
          <label class="text-neutral-400 block mb-1">Job URL *</label>
          <input id="new-url" class="w-full bg-charcoal-950 border border-charcoal-700 rounded px-3 py-2 text-neutral-200 outline-none focus:border-neutral-500" placeholder="https://..." />
        </div>
        <div>
          <label class="text-neutral-400 block mb-1">Location</label>
          <input id="new-loc" class="w-full bg-charcoal-950 border border-charcoal-700 rounded px-3 py-2 text-neutral-200 outline-none focus:border-neutral-500" placeholder="Remote / Bengaluru" value="Remote" />
        </div>
        <div>
          <label class="text-neutral-400 block mb-1">Notes / Snippet</label>
          <textarea id="new-desc" rows="2" class="w-full bg-charcoal-950 border border-charcoal-700 rounded px-3 py-2 text-neutral-200 outline-none focus:border-neutral-500" placeholder="Target stack requirements, referral contact..."></textarea>
        </div>
      </div>
      <div class="flex justify-end gap-2 pt-2">
        <button onclick="closeModal()" class="px-3 py-1.5 rounded text-xs font-mono text-neutral-400 hover:bg-charcoal-800">Cancel</button>
        <button onclick="submitManualJob()" class="px-4 py-1.5 rounded text-xs font-mono bg-emerald-950 text-emerald-300 border border-emerald-800 hover:bg-emerald-900/60">Save Job</button>
      </div>
    </div>
  </div>

  <script>
    let activeFilter = 'all';

    function formatTime(isoString) {
      if (!isoString) return 'recently';
      try {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
        if (diffHrs < 1) return 'just now';
        if (diffHrs < 24) return `${diffHrs}h ago`;
        const diffDays = Math.floor(diffHrs / 24);
        return `${diffDays}d ago`;
      } catch (e) {
        return 'recently';
      }
    }

    async function purgeJunk() {
  if (!confirm('Purge all unreviewed postings with score < 50% and non-English titles?')) return;
  const res = await fetch('/api/maintenance/purge-junk', { method: 'POST' });
  const data = await res.json();
  alert(`Purged ${data.purged_count} low-value / noisy postings!`);
  fetchStats();
  loadJobs(activeFilter);
}


    async function fetchStats() {
      const res = await fetch('/api/stats');
      const data = await res.json();
      const b = data.breakdown || {};
      document.getElementById('stats-bar').innerHTML = `
        <div class="bg-charcoal-900 px-3 py-1.5 rounded-lg border border-charcoal-700/50 text-right">
          <span class="text-[10px] uppercase font-mono tracking-wider text-neutral-500 block">Total</span>
          <p class="text-sm font-semibold text-neutral-200">${data.total}</p>
        </div>
        <div class="bg-charcoal-900 px-3 py-1.5 rounded-lg border border-charcoal-700/50 text-right">
          <span class="text-[10px] uppercase font-mono tracking-wider text-neutral-500 block">Matches</span>
          <p class="text-sm font-semibold text-indigo-400">${data.matches}</p>
        </div>
        <div class="bg-charcoal-900 px-3 py-1.5 rounded-lg border border-charcoal-700/50 text-right">
          <span class="text-[10px] uppercase font-mono tracking-wider text-neutral-500 block">Applied</span>
          <p class="text-sm font-semibold text-emerald-400">${b.applied || 0}</p>
        </div>
        <div class="bg-charcoal-900 px-3 py-1.5 rounded-lg border border-charcoal-700/50 text-right">
          <span class="text-[10px] uppercase font-mono tracking-wider text-neutral-500 block">Saved</span>
          <p class="text-sm font-semibold text-amber-400">${b.saved || 0}</p>
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
  <div class="bg-charcoal-900 border border-charcoal-700/60 rounded-xl p-5 flex flex-col justify-between hover:border-charcoal-600 transition-colors shadow-sm h-[290px]">
    <div class="space-y-2.5 overflow-hidden">
      <div class="flex justify-between items-center">
        <span class="text-[11px] font-mono px-2 py-0.5 rounded-md font-medium ${
          j.match_score >= 80 ? 'bg-emerald-950/70 text-emerald-400 border border-emerald-800/60' :
          j.match_score >= 60 ? 'bg-indigo-950/70 text-indigo-300 border border-indigo-800/60' :
          'bg-charcoal-800 text-neutral-400 border border-charcoal-700'
        }">Score: ${j.match_score}</span>
        <div class="flex items-center gap-2">
          <span class="text-[10px] font-mono text-neutral-500">${formatTime(j.created_at)}</span>
          <span class="text-[10px] font-mono text-neutral-500 uppercase tracking-wider">&bull; ${j.source || 'web'}</span>
        </div>
      </div>

      <div>
        <h2 class="font-semibold text-sm text-neutral-100 leading-snug truncate" title="${j.position}">${j.position}</h2>
        <p class="text-xs text-neutral-400 mt-0.5 truncate">${j.company} &bull; <span class="text-neutral-500">${j.location}</span></p>
      </div>

      <p class="text-xs text-neutral-400/80 line-clamp-3 leading-relaxed font-normal">${j.description || 'No summary text available.'}</p>
    </div>

    <div class="pt-3 border-t border-charcoal-800 flex items-center justify-between shrink-0">
      <a href="${j.url}" target="_blank" class="text-xs font-mono text-indigo-400 hover:text-indigo-300 transition-colors">
        Open Link &rarr;
      </a>
      <div class="flex gap-1.5 items-center">
        <button onclick="setStatus('${j.id}', 'saved')" class="text-xs font-mono px-2 py-1 rounded bg-charcoal-800 hover:bg-charcoal-700 text-amber-300/90 border border-charcoal-700">Save</button>
        <button onclick="setStatus('${j.id}', 'applied')" class="text-xs font-mono px-2 py-1 rounded bg-charcoal-800 hover:bg-charcoal-700 text-emerald-400/90 border border-charcoal-700">Apply</button>
        <button onclick="setStatus('${j.id}', 'pass')" class="text-xs font-mono px-2 py-1 rounded bg-charcoal-800 hover:bg-charcoal-700 text-neutral-400 border border-charcoal-700">Pass</button>
        <button onclick="deleteJob('${j.id}')" class="text-xs px-2 py-1 rounded bg-charcoal-800 hover:bg-rose-950/40 text-rose-400 border border-charcoal-700" title="Delete record">&times;</button>
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

    async function deleteJob(jobId) {
      if (!confirm('Remove this job record completely?')) return;
      await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
      fetchStats();
      loadJobs(activeFilter);
    }

    async function pruneDatabase() {
      const res = await fetch('/api/maintenance/prune', { method: 'POST' });
      const data = await res.json();
      alert(`Cleaned up ${data.duplicates_purged} cross-platform duplicates!`);
      fetchStats();
      loadJobs(activeFilter);
    }

    function openModal() {
      document.getElementById('add-modal').classList.remove('hidden');
      document.getElementById('add-modal').classList.add('flex');
    }

    function closeModal() {
      document.getElementById('add-modal').classList.add('hidden');
      document.getElementById('add-modal').classList.remove('flex');
    }

    async function submitManualJob() {
      const position = document.getElementById('new-pos').value.trim();
      const company = document.getElementById('new-comp').value.trim();
      const url = document.getElementById('new-url').value.trim();
      const location = document.getElementById('new-loc').value.trim();
      const description = document.getElementById('new-desc').value.trim();

      if (!position || !company || !url) {
        alert('Position, Company, and URL are required.');
        return;
      }

      await fetch('/api/jobs/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position, company, url, location, description })
      });

      closeModal();
      document.getElementById('new-pos').value = '';
      document.getElementById('new-comp').value = '';
      document.getElementById('new-url').value = '';
      document.getElementById('new-desc').value = '';
      fetchStats();
      loadJobs(activeFilter);
    }

    fetchStats();
    loadJobs('all');
  </script>
</body>
</html>
    """
@app.post("/api/maintenance/purge-junk")
def purge_junk():
    return db.purge_low_score_and_junk(min_score=50)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("dashboard:app", host="127.0.0.1", port=8000, reload=True)