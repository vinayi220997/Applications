import json, sys
from unittest import mock
sys.path.insert(0, ".")
from jobradar import db as dbm, pipeline as pl, intake
from jobradar.sources import ats, boards
from jobradar.normalize import iso, now_utc
from datetime import timedelta
h = lambda n: iso(now_utc()-timedelta(hours=n))
gh = {"jobs":[
 {"id":101,"title":"Backend Engineer II","updated_at":h(5),"first_published":h(5),"requisition_id":"R-1","location":{"name":"Bengaluru, Karnataka, India"},"absolute_url":"https://job-boards.greenhouse.io/acme/jobs/101","content":"&lt;p&gt;Build payment APIs in Python and Django on AWS. 3-5 years of experience. PostgreSQL, Kafka.&lt;/p&gt;"},
 {"id":102,"title":"Senior Software Engineer, Payments","updated_at":h(60),"first_published":h(60),"location":{"name":"Remote - India"},"absolute_url":"https://job-boards.greenhouse.io/acme/jobs/102","content":"&lt;p&gt;Python, AWS, Kubernetes. 4+ years of experience.&lt;/p&gt;"},
 {"id":103,"title":"Principal Engineer","updated_at":h(5),"location":{"name":"Bengaluru"},"absolute_url":"https://x/103","content":"10+ years experience"},
 {"id":104,"title":"Backend Developer","updated_at":h(5),"location":{"name":"Hyderabad, India"},"absolute_url":"https://job-boards.greenhouse.io/acme/jobs/104","content":"&lt;p&gt;Django REST, Python. 2-4 years experience.&lt;/p&gt;"}]}
lv = [{"id":"abc","text":"Software Engineer - Backend","categories":{"location":"Bangalore","commitment":"Full-time"},"workplaceType":"hybrid","createdAt":int((now_utc()-timedelta(days=5)).timestamp()*1000),"hostedUrl":"https://jobs.lever.co/beta/abc","applyUrl":"https://jobs.lever.co/beta/abc/apply","descriptionPlain":"We use Python, Django and AWS. Minimum 3 years of experience.","lists":[],"salaryRange":{"min":2500000,"max":3500000,"currency":"INR","interval":"per-year-salary"}}]
rem = {"jobs":[{"id":9,"url":"https://remotive.com/remote-jobs/software-dev/backend-python-9","title":"Backend Python Engineer","company_name":"Gamma","job_type":"full_time","publication_date":h(30),"candidate_required_location":"Worldwide","salary":"","description":"<p>Python, Django, AWS. 3+ years of experience.</p>"}]}
def fake_get_json(url, timeout=20, retries=2, headers=None):
    if "greenhouse.io/v1/boards/acme/jobs" in url: return gh
    if "greenhouse.io/v1/boards/acme" in url: return {"name":"Acme Pay"}
    if "lever.co/v0/postings/beta" in url: return lv
    if "remotive.com" in url: return rem
    from jobradar.http import FetchError; raise FetchError("HTTP 404",404)
with mock.patch("jobradar.sources.ats.get_json", fake_get_json), mock.patch("jobradar.sources.boards.get_json", fake_get_json), \
     mock.patch.object(pl, "online", return_value=True), \
     mock.patch.object(pl, "load_company_candidates", return_value=[{"ats":"greenhouse","token":"acme"},{"ats":"lever","token":"beta"},{"ats":"ashby","token":"nope"}]), \
     mock.patch.dict(boards.BOARDS, {"remotive": boards.remotive}, clear=True), \
     mock.patch("jobradar.verify.fetch", return_value=(200,"https://remotive.com/remote-jobs/software-dev/backend-python-9","<h1>Backend Python Engineer</h1>")):
    with dbm.session() as c:
        p = intake.finalize({"roles":["backend developer"],"skills":["python","django","aws"],"experience":"3–5 years","locations":["Bengaluru"],"remote_international":True,"work_arrangement":"any","industries":["fintech"],"min_salary":"18 LPA","email":"","name":"Dilip – backend","description":"Backend developer"})
        c.execute("INSERT INTO profiles(name,email,email_on,active,profile_json) VALUES (?,?,1,1,?)",(p["name"],"",json.dumps(p)))
    pl.run("demo", send=False)
