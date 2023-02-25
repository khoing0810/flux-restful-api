import json
import os
import pwd
import subprocess

# Terminal functions to handle submitting on behalf of a user

job_format = "{id.f58:>12} {username:<8.8} {name:<10.10+} {status:>9.9} {ntasks:>6} {nnodes:>6h} {t_submit!d:%b%d %R::>12} {t_remaining!F:>12h} {contextual_time!F:>8h}"
fields = [
    "id",
    "user",
    "name",
    "status",
    "ntasks",
    "nnodes",
    "time_submit",
    "time_remaining",
    "time_contextual",
]


class JobId:
    """
    A fake Flux Future that can return a job_id
    """

    def __init__(self, jobid):
        self.job_id = jobid

    def get_id(self):
        return self.job_id


def run_as_user(command, user, cwd=None, request_env=None):
    """
    Run a command as a user
    """
    pw_record = pwd.getpwnam(user)
    user_name = pw_record.pw_name
    user_uid = pw_record.pw_uid
    user_gid = pw_record.pw_gid

    # Even for a user this should be populated with dummy paths, etc.
    env = {}

    # cwd will bork on an empty string
    cwd = cwd or None

    print(f"🧾️ Running command as {user_name}")
    env["HOME"] = pw_record.pw_dir
    env["LOGNAME"] = user_name
    env["USER"] = pw_record.pw_name

    # Update the environment, if provided
    if request_env is not None:
        env.update(request_env)

    # Run command as the user
    print("⭐️ " + " ".join(command))
    print(cwd)
    print(env)
    process = subprocess.Popen(
        command,
        preexec_fn=demote(user_uid, user_gid),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
    )

    # Let the calling function handle the return value parsing
    return process.communicate()


def job_list(user):
    """
    List jobs for a user
    """


def submit_job(jobspec, user):
    """
    Submit a job on behalf of a user.
    """
    # Prepare the command
    command = ["flux", "mini", "submit"]
    for resource in jobspec.resources:
        if resource["with"][0]["type"] == "core":
            command += ["--cores", str(resource["count"])]

    for cmd in jobspec.tasks:
        if "command" in cmd:
            command += cmd["command"]
            break

    # Flux submit as the user
    result = run_as_user(
        command, request_env=jobspec.environment, user=user, cwd=jobspec.cwd
    )
    jobid = (result[0].decode("utf-8")).strip()
    return JobId(jobid)


def cancel_job(jobid, user):
    """
    Cancel a job for a user
    """
    command = ["flux", "job", "cancel", jobid]
    result = run_as_user(command, user=user)
    jobid = (result[0].decode("utf-8")).strip()
    if "inactive" in jobid:
        return "Job cannot be cancelled: %s." % jobid, 400
    return "Job is requested to cancel.", 200


def get_job_output(jobid, user, delay=None):
    """
    Given a jobid, get the output.

    If there is a delay, we are requesting on demand, so we want to return early.
    """
    lines = []
    command = ["flux", "job", "info", jobid, "guest.output"]
    result = run_as_user(command, user=user)
    lines = (result[0].decode("utf-8")).strip()

    output = ""
    for line in lines.split("\n"):
        try:
            content = json.loads(line)
            if "context" in content and "data" in content["context"]:
                output += content["context"]["data"]
        except Exception:
            print(line)
            pass
    return output


def demote(user_uid, user_gid):
    """
    Demote the user to a specific gid/gid
    """

    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)

    return result


def get_job(jobid, user):
    """
    Get details for a job

    This is not currently used, instead we pass a user to job list.
    """
    command = ["flux", "jobs", jobid, "-o", job_format, "--suppress-header"]
    result = run_as_user(command, user=user)
    jobid = (result[0].decode("utf-8")).strip()
    jobid = [x for x in jobid.split(" ") if x]
    jobinfo = {}
    for field in fields:
        jobinfo[field] = jobid.pop(0)
    return jobinfo
