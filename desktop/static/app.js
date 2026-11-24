"use strict";
const $ = (id) => document.getElementById(id);
let page = 1,
  visitor = "",
  token = "",
  configured = false,
  lookupVersion = 0,
  currentUser = null,
  serverOffset = 0,
  selectedProfile = null,
  searchTerm = "",
  searchMode = "auto",
  searchPage = 1,
  searchTotal = 0,
  editRecord = null;
function freshToken() {
  token = crypto.randomUUID
    ? crypto.randomUUID()
    : Array.from(crypto.getRandomValues(new Uint8Array(24)), (x) =>
        x.toString(16).padStart(2, "0"),
      ).join("");
}
function toast(s, error = false) {
  $("message").textContent = s;
  $("message").className = error ? "error" : "";
  $("message").hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => ($("message").hidden = true), 6500);
}
async function api(path, data) {
  const saving =
    !!data &&
    [
      "/api/visit",
      "/api/out",
      "/api/call",
      "/api/edit-visit",
      "/api/profile",
      "/api/edit-call",
    ].includes(path);
  if (saving) {
    $("saveStatus").className = "hint";
    $("saveStatus").textContent =
      "Saving… Please wait for database confirmation.";
  }
  let r = await fetch(
    path,
    data
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-MMI": "1" },
          body: JSON.stringify(data),
        }
      : {},
  ).catch((e) => {
    if (saving) {
      $("saveStatus").className = "hint failed";
      $("saveStatus").textContent =
        "Save not confirmed. Check connection, then retry the same entry.";
    }
    checkLive();
    throw e;
  });
  let j = await r.json();
  if (
    data &&
    [
      "/api/visit",
      "/api/out",
      "/api/call",
      "/api/edit-visit",
      "/api/profile",
      "/api/edit-call",
    ].includes(path)
  ) {
    if (r.ok) {
      $("saveStatus").className = "hint saved";
      $("saveStatus").textContent =
        "Saved to database · " +
        stamp(new Date(Date.now() + serverOffset)) +
        (j.backup_warning
          ? " · Excel backup warning: " + j.backup_warning
          : " · Excel backup updated");
      checkLive();
    } else {
      $("saveStatus").className = "hint failed";
      $("saveStatus").textContent =
        "Entry not saved: " + (j.error || "Please retry.");
    }
  }
  if (!r.ok) {
    if (r.status === 401) await status();
    throw Error(j.error || "Request failed");
  }
  if (j.backup_warning) toast(j.backup_warning, true);
  return j;
}
function stamp(s) {
  return new Date(s).toLocaleString("en-GB", {
    timeZone: "Asia/Karachi",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}
async function status() {
  let s = await api("/api/status");
  configured = s.configured;
  currentUser = s.user;
  serverOffset = new Date(s.serverTime).getTime() - Date.now();
  document.body?.classList?.toggle("signedIn", s.loggedIn);
  $("appSidebar").hidden = !s.loggedIn;
  $("liveStatus").hidden = !s.loggedIn;
  $("auth").hidden = s.loggedIn;
  $("workspace").hidden = !s.loggedIn;
  $("logout").hidden = !s.loggedIn;
  $("authTitle").textContent = configured
    ? "Staff sign in"
    : "Create administrator login";
  $("authHelp").textContent = configured
    ? "Enter the login ID and password provided by your admin."
    : "Create your admin ID and password (minimum 10 characters). Admin can then create receptionist logins.";
  $("oldPasswordLabel").hidden = configured || !s.upgrade;
  if (!s.loggedIn) {
    showPage("visitor");
    $("workspaceTitle").textContent = "Reception workspace";
    $("tabAdmin").hidden = true;
    $("editPanel").hidden = true;
    $("changePanel").hidden = true;
  }
  if (s.loggedIn) {
    $("identity").textContent =
      "Signed in: " +
      s.user.name +
      " (" +
      s.user.username +
      ") · " +
      s.user.role +
      " · Signed in: " +
      stamp(s.user.login_at) +
      " · System started: " +
      stamp(s.started);
    $("tabAdmin").hidden = s.user.role !== "admin";
    $("userDisplay").textContent = s.user.name;
    $("userRoleDisplay").textContent = s.user.role;
    $("userAvatar").textContent = s.user.name
      .split(/\s+/)
      .map((n) => n[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();
    $("backupMenu").hidden = s.user.role !== "admin";
    $("callStaff").value = s.user.name;
    for (let id of ["allBackup", "restoreBackup"])
      $(id).hidden = s.user.role !== "admin";
    const prev = s.user.previous_login;
    if (prev)
      $("identity").textContent +=
        " · Previous login: " +
        stamp(prev.login_at) +
        " · Previous logout: " +
        (prev.logout_at
          ? stamp(prev.logout_at)
          : prev.end_reason || "Not recorded");
    await load();
    checkLive();
  }
}
$("authForm").onsubmit = async (e) => {
  e.preventDefault();
  $("authSubmit").disabled = true;
  $("authSubmit").textContent = "Signing you in…";
  try {
    await api(configured ? "/api/login" : "/api/setup", {
      username: $("username").value,
      password: $("password").value,
      old_password: $("oldPassword").value,
    });
    $("password").value = "";
    $("oldPassword").value = "";
    await status();
  } catch (e) {
    toast(e.message, true);
  } finally {
    $("authSubmit").disabled = false;
    $("authSubmit").textContent = "Continue to workspace →";
  }
};
$("logout").onclick = async () => {
  try {
    await api("/api/logout", {});
    currentUser = null;
    callStart = 0;
    calls = [];
    callPage = 1;
    editingCall = null;
    $("callMatches").replaceChildren();
    $("moreCallMatches").hidden = true;
    $("callSearch").value = "";
    $("callDate").value = "";
    callLookupVersion++;
    visitor = "";
    selectedProfile = null;
    $("saveProfile").hidden = true;
    $("profileReasonLabel").hidden = true;
    $("moreMatches").hidden = true;
    $("selected").textContent = "NEW VISITOR · Enter details below";
    $("callReasonLabel").hidden = true;
    $("callSave").textContent = "Save call record";
    $("message").hidden = true;
    clearTimeout(toast.timer);
    $("saveStatus").className = "hint save-banner";
    $("editPanel").hidden = true;
    $("changePanel").hidden = true;
    page = 1;
    $("visitForm").reset();
    $("lookup").value = "";
    $("matches").replaceChildren();
    $("rows").replaceChildren();
    $("callRows").replaceChildren();
    $("callForm").reset();
    $("userForm").reset();
    $("users").replaceChildren();
    $("audit").replaceChildren();
    $("callAt").value = "";
    $("historyNotice").hidden = true;
    $("saveStatus").textContent = "Waiting for next entry.";
    freshToken();
    showPage("visitor");
    await status();
  } catch (e) {
    toast(e.message, true);
  }
};
function debounce(fn, delay = 250) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
async function lookup(term, mode = "auto", append = false) {
  const version = ++lookupVersion;
  if (!append) {
    searchTerm = term;
    searchMode = mode;
    searchPage = 1;
    $("matches").replaceChildren();
  }
  try {
    let response = await api(
      "/api/search?" +
        new URLSearchParams({ q: term, mode, paged: "1", page: searchPage }),
    );
    if (version !== lookupVersion) return;
    searchTotal = response.total;
    for (let v of response.rows) {
      let b = document.createElement("button");
      b.type = "button";
      b.className = "match";
      let name = document.createElement("b");
      name.textContent = v.name;
      b.append(
        name,
        document.createTextNode(
          v.mobile + " · " + v.cnic + " · " + v.visits + " visits",
        ),
      );
      b.onclick = () => select(v);
      $("matches").append(b);
    }
    $("moreMatches").hidden = searchPage * 30 >= searchTotal;
    $("moreMatches").textContent = "Show more · " + searchTotal + " matches";
  } catch (e) {
    toast(e.message, true);
  }
}
$("lookup").oninput = debounce(() => lookup($("lookup").value), 120);
$("moreMatches").onclick = () => {
  searchPage++;
  lookup(searchTerm, searchMode, true);
};
for (let [id, mode] of [
  ["mobile", "phone"],
  ["cnic", "cnic"],
  ["name", "name"],
])
  $(id).addEventListener(
    "input",
    debounce(() => lookup($(id).value, mode), 120),
  );
function select(v) {
  lookupVersion++;
  selectedProfile = v;
  for (let id of ["mobile", "name", "cnic"]) $(id).value = v[id];
  const last = v.last_details;
  for (let id of ["host", "purpose", "remarks"]) $(id).value = last?.[id] || "";
  $("matches").replaceChildren();
  $("moreMatches").hidden = true;
  $("profileReasonLabel").hidden = false;
  $("saveProfile").hidden = false;
  $("profileReason").value = "";
  $("selected").textContent =
    "Returning visitor · " +
    v.visits +
    " previous visits · Last IN: " +
    (v.last_visit ? stamp(v.last_visit) : "None") +
    (last
      ? " · Last OUT: " +
        (last.out_at ? stamp(last.out_at) : "Not recorded") +
        " · Saved by: " +
        last.staff
      : "");
  visitor = String(v.id);
  page = 1;
  $("date").value = "";
  $("filter").value = "";
  $("historyNotice").hidden = false;
  $("historyNotice").textContent =
    "Complete history for " +
    v.name +
    " · Last meeting/purpose/remarks copied for editing";
  freshToken();
  load();
  $("host").focus();
}
function clear() {
  lookupVersion++;
  selectedProfile = null;
  $("saveProfile").hidden = true;
  $("profileReasonLabel").hidden = true;
  $("moreMatches").hidden = true;
  $("visitForm").reset();
  $("lookup").value = "";
  $("matches").replaceChildren();
  $("selected").textContent = "New visitor · Enter details below";
  visitor = "";
  $("historyNotice").hidden = true;
  freshToken();
  page = 1;
  load();
  $("mobile").focus();
}
$("clear").onclick = clear;
$("visitForm").onsubmit = async (e) => {
  e.preventDefault();
  $("save").disabled = true;
  try {
    let d = {
      token,
      visitor_id: selectedProfile?.id,
      profile_version: selectedProfile?.version,
    };
    for (let id of ["mobile", "name", "cnic", "purpose", "host", "remarks"])
      d[id] = $(id).value;
    let r = await api("/api/visit", d);
    toast(r.backup_warning || r.message, !!r.backup_warning);
    clear();
  } catch (e) {
    toast(e.message, true);
  } finally {
    $("save").disabled = false;
  }
};
function params() {
  return new URLSearchParams({
    page,
    date: $("date").value,
    q: $("filter").value,
    visitor,
  });
}
let historyVersion = 0;
async function load() {
  let version = ++historyVersion;
  try {
    let r = await api("/api/visits?" + params());
    if (version !== historyVersion) return;
    $("rows").replaceChildren();
    for (let v of r.rows) {
      let tr = document.createElement("tr");
      for (let content of [
        v.name,
        [v.mobile, v.cnic],
        [
          stamp(v.at),
          v.out_at
            ? "OUT: " + stamp(v.out_at)
            : v.staff
              ? "Currently IN"
              : "Historical · OUT unknown",
        ],
        [
          v.host || "—",
          (v.purpose || "—") + " · Remarks: " + (v.remarks || "—"),
        ],
      ]) {
        let td = document.createElement("td");
        if (Array.isArray(content)) {
          td.textContent = content[0];
          let sub = document.createElement("span");
          sub.textContent = content[1];
          td.append(sub);
        } else td.textContent = content;
        tr.append(td);
      }
      let td = document.createElement("td");
      if (!v.out_at && v.staff) {
        let btn = document.createElement("button");
        btn.textContent = "OUT";
        btn.className = "out-button";
        btn.onclick = async () => {
          btn.disabled = true;
          try {
            await api("/api/out", { id: v.id });
            toast("OUT time saved.");
            await load();
          } catch (e) {
            btn.disabled = false;
            toast(e.message, true);
          }
        };
        td.append(btn);
      } else {
        let pill = document.createElement("span");
        pill.className = "status-pill";
        pill.textContent = v.out_at ? "Completed" : "Historical";
        td.append(pill);
      }
      let edit = document.createElement("button");
      edit.textContent = "Edit";
      edit.onclick = () => openEdit(v);
      td.append(edit);
      let changes = document.createElement("button");
      changes.textContent = "Changes";
      changes.onclick = () => showChanges("visit", v.id);
      td.append(changes);
      let staff = document.createElement("span");
      staff.textContent =
        "Saved: " +
        (v.staff || "Legacy") +
        (v.out_by ? " · OUT: " + v.out_by : "") +
        (v.updated_by ? " · Updated: " + v.updated_by : "");
      td.append(staff);
      tr.append(td);
      $("rows").append(tr);
    }
    if (!r.rows.length) {
      let tr = document.createElement("tr");
      let td = document.createElement("td");
      td.colSpan = 5;
      td.className = "empty-state";
      td.textContent =
        "Your next welcome starts here. Saved visits will appear in this history.";
      tr.append(td);
      $("rows").append(tr);
    }
    for (let id of ["today", "people", "inside"])
      $(id).textContent = r.stats[id];
    $("pageLabel").textContent =
      "Page " +
      page +
      " of " +
      Math.max(1, Math.ceil(r.total / 30)) +
      " · " +
      r.total +
      " visits";
    $("prev").disabled = page === 1;
    $("next").disabled = page * 30 >= r.total;
    $("export").href = "/api/export?" + params();
    $("printHistory").href = "/api/print?" + params();
  } catch (e) {
    toast(e.message, true);
  }
}
$("filter").oninput = debounce(() => {
  page = 1;
  load();
});
$("date").onchange = () => {
  page = 1;
  load();
};
$("resetFilter").onclick = () => {
  $("date").value = "";
  $("filter").value = "";
  visitor = "";
  $("historyNotice").hidden = true;
  page = 1;
  load();
};
$("prev").onclick = () => {
  page--;
  load();
};
$("next").onclick = () => {
  page++;
  load();
};
function clock() {
  $("clock").textContent = stamp(new Date(Date.now() + serverOffset)) + " PKT";
}
clock();
setInterval(clock, 1000);
freshToken();
status().catch((e) => toast(e.message, true));
function showPage(which) {
  window.scrollTo?.({ top: 0, behavior: "instant" });
  for (let x of ["visitor", "call", "admin"])
    $(x + "Page").hidden = x !== which;
  for (let [id, x] of [
    ["tabVisitors", "visitor"],
    ["tabCalls", "call"],
    ["tabAdmin", "admin"],
  ]) {
    $(id).className = "nav-item" + (x === which ? " active" : "");
    if (x === which) $(id).setAttribute?.("aria-current", "page");
    else $(id).removeAttribute?.("aria-current");
  }
  $("workspaceTitle").textContent = {
    visitor: "Visitor desk",
    call: "Telephone & callbacks",
    admin: "Administration",
  }[which];
  $("editPanel").hidden = true;
  $("changePanel").hidden = true;
  if (which === "call") loadCalls();
  if (which === "admin") loadUsers();
}
$("tabVisitors").onclick = () => showPage("visitor");
$("tabCalls").onclick = () => showPage("call");
$("tabAdmin").onclick = () => showPage("admin");
function callNow() {
  return new Date(Date.now() + serverOffset + 5 * 3600000)
    .toISOString()
    .slice(0, 19);
}
let callStart = 0,
  callToken = "",
  calls = [],
  editingCall = null,
  callPage = 1,
  callTotal = 0,
  callVersion = 0,
  callLookupVersion = 0,
  callLookupPage = 1,
  callLookupTerm = "",
  callLookupMode = "phone";
function resetCall() {
  editingCall = null;
  $("callMatches").replaceChildren();
  $("moreCallMatches").hidden = true;
  callLookupVersion++;
  $("callReasonLabel").hidden = true;
  $("callSave").textContent = "Save call record";
  callStart = 0;
  $("callForm").reset();
  $("callAt").value = callNow();
  $("callStaff").value = currentUser?.name || "";
  $("callTimer").textContent = "00:00";
  callToken =
    "call-" +
    Array.from(crypto.getRandomValues(new Uint8Array(16)), (x) =>
      x.toString(16).padStart(2, "0"),
    ).join("");
}
$("startCall").onclick = () => {
  if (callStart) {
    toast("Call timer already running.", true);
    return;
  }
  callStart = Date.now() + serverOffset;
  $("callAt").value = callNow();
  $("callDuration").value = 0;
};
$("endCall").onclick = () => {
  if (!callStart) {
    toast("Start the timer first, or enter duration manually.", true);
    return;
  }
  $("callDuration").value = Math.max(
    0,
    Math.round((Date.now() + serverOffset - callStart) / 1000),
  );
  callStart = 0;
  toast("Call ended. Complete remarks and save.");
};
setInterval(() => {
  if (callStart) {
    let d = Math.max(
      0,
      Math.round((Date.now() + serverOffset - callStart) / 1000),
    );
    $("callTimer").textContent =
      Math.floor(d / 60) + ":" + String(d % 60).padStart(2, "0");
    $("callDuration").value = d;
  }
}, 1000);
$("clearCall").onclick = resetCall;
$("callForm").onsubmit = async (e) => {
  e.preventDefault();
  let btn = e.submitter || $("callForm").querySelector(".primary");
  btn.disabled = true;
  try {
    if (callStart) throw Error("End the call timer before saving.");
    const result = await api(editingCall ? "/api/edit-call" : "/api/call", {
      id: editingCall?.id,
      version: editingCall?.version,
      reason: $("callReason").value,
      phone: $("callPhone").value,
      caller: $("callCaller").value,
      at: $("callAt").value + "+05:00",
      duration: Number($("callDuration").value),
      spoken_by: $("callStaff").value,
      kind: $("callKind").value,
      remarks: $("callRemarks").value,
      token: callToken,
    });
    toast(
      result.backup_warning || "Call record saved.",
      !!result.backup_warning,
    );
    callPage = 1;
    resetCall();
    await loadCalls();
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
  }
};
function visibleCalls() {
  return calls;
}
function renderCalls() {
  $("callRows").replaceChildren();
  for (let c of visibleCalls()) {
    let tr = document.createElement("tr");
    for (let content of [
      [c.caller || c.kind, c.phone],
      [stamp(c.at), c.duration + " seconds · " + c.kind],
      [c.spoken_by, "Saved by " + c.staff],
      c.remarks || "—",
    ]) {
      let td = document.createElement("td");
      if (Array.isArray(content)) {
        td.textContent = content[0];
        let sub = document.createElement("span");
        sub.textContent = content[1];
        td.append(sub);
      } else td.textContent = content;
      tr.append(td);
    }
    let action = document.createElement("td");
    let edit = document.createElement("button");
    edit.textContent = "Edit";
    edit.onclick = () => {
      editingCall = c;
      callStart = 0;
      $("callPhone").value = c.phone;
      $("callCaller").value = c.caller;
      $("callAt").value = new Date(new Date(c.at).getTime() + 5 * 3600000)
        .toISOString()
        .slice(0, 19);
      $("callDuration").value = c.duration;
      $("callStaff").value = c.spoken_by;
      $("callKind").value = c.kind;
      $("callRemarks").value = c.remarks;
      $("callReason").value = "";
      $("callReasonLabel").hidden = false;
      $("callSave").textContent = "Save call correction";
      $("callPhone").focus();
    };
    action.append(edit);
    let changes = document.createElement("button");
    changes.textContent = "Changes";
    changes.onclick = () => showChanges("call", c.id);
    action.append(changes);
    tr.append(action);
    $("callRows").append(tr);
  }
}
function callParams() {
  return new URLSearchParams({
    q: $("callSearch").value,
    date: $("callDate").value,
    page: callPage,
    paged: "1",
  });
}
async function loadCalls() {
  const version = ++callVersion;
  try {
    const response = await api("/api/calls?" + callParams());
    if (version !== callVersion) return;
    calls = response.rows;
    callTotal = response.total;
    renderCalls();
    if (!calls.length) {
      let tr = document.createElement("tr"),
        td = document.createElement("td");
      td.colSpan = 5;
      td.className = "empty-state";
      td.textContent =
        "Keep the conversation going. Saved calls will appear here.";
      tr.append(td);
      $("callRows").append(tr);
    }
    $("callPrev").disabled = callPage === 1;
    $("callNext").disabled = callPage * 30 >= callTotal;
    $("callPageLabel").textContent =
      "Page " +
      callPage +
      " of " +
      Math.max(1, Math.ceil(callTotal / 30)) +
      " · " +
      callTotal +
      " calls";
    $("printCalls").href = "/api/call-print?" + callParams();
    if (!$("callAt").value) resetCall();
  } catch (e) {
    toast(e.message, true);
  }
}
$("callSearch").oninput = debounce(() => {
  callPage = 1;
  loadCalls();
}, 150);
$("callDate").onchange = () => {
  callPage = 1;
  loadCalls();
};
$("callPrev").onclick = () => {
  callPage--;
  loadCalls();
};
$("callNext").onclick = () => {
  callPage++;
  loadCalls();
};
$("resetCalls").onclick = () => {
  $("callSearch").value = "";
  $("callDate").value = "";
  callPage = 1;
  loadCalls();
};
$("exportCalls").onclick = () => {
  window.location.href = "/api/call-export?" + callParams();
};
async function lookupCall(term, mode = "phone", append = false) {
  const version = ++callLookupVersion;
  if (!append) {
    callLookupPage = 1;
    callLookupTerm = term;
    callLookupMode = mode;
    $("callMatches").replaceChildren();
  }
  try {
    const response = await api(
      "/api/caller-search?" +
        new URLSearchParams({ q: term, mode, page: callLookupPage }),
    );
    if (version !== callLookupVersion) return;
    for (let c of response.rows) {
      let b = document.createElement("button");
      b.type = "button";
      b.className = "match";
      let name = document.createElement("b");
      name.textContent = c.caller || "Saved caller";
      b.append(
        name,
        document.createTextNode(
          c.phone +
            (c.last_details
              ? " · Last call: " + stamp(c.last_details.at)
              : " · Visitor directory"),
        ),
      );
      b.onclick = () => {
        $("callPhone").value = c.phone;
        $("callCaller").value = c.caller;
        if (c.last_details)
          $("callRemarks").value = c.last_details.remarks || "";
        callLookupVersion++;
        $("callMatches").replaceChildren();
        $("moreCallMatches").hidden = true;
        $("callRemarks").focus();
      };
      $("callMatches").append(b);
    }
    $("moreCallMatches").hidden = callLookupPage * 30 >= response.total;
    $("moreCallMatches").textContent =
      "Show more · " + response.total + " callers";
  } catch (e) {
    toast(e.message, true);
  }
}
$("callPhone").addEventListener(
  "input",
  debounce(() => lookupCall($("callPhone").value), 120),
);
$("callCaller").addEventListener(
  "input",
  debounce(() => lookupCall($("callCaller").value, "name"), 120),
);
$("moreCallMatches").onclick = () => {
  callLookupPage++;
  lookupCall(callLookupTerm, callLookupMode, true);
};
async function loadUsers() {
  try {
    let users = await api("/api/users");
    $("users").replaceChildren();
    for (let u of users) {
      let b = document.createElement("button");
      b.className = "match";
      b.textContent =
        u.username +
        " · " +
        u.name +
        " · " +
        u.role +
        " · " +
        (u.active ? "Active" : "Disabled");
      b.onclick = () => {
        $("userId").value = u.username;
        $("userName").value = u.name;
        $("userRole").value = u.role;
        $("userActive").value = u.active ? "1" : "0";
        $("userPassword").value = "";
      };
      $("users").append(b);
    }
    let audit = await api("/api/audit");
    $("audit").replaceChildren();
    for (let r of audit) {
      let p = document.createElement("p");
      p.className = "muted";
      p.textContent =
        r.username +
        " · IN " +
        stamp(r.login_at) +
        " · " +
        (r.logout_at
          ? "OUT " + stamp(r.logout_at)
          : r.end_reason || "Signed in / no explicit sign-out") +
        " · Last activity: " +
        (r.last_seen ? stamp(r.last_seen) : "Unknown");
      $("audit").append(p);
    }
  } catch (e) {
    toast(e.message, true);
  }
}
$("userForm").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("/api/user", {
      username: $("userId").value,
      name: $("userName").value,
      role: $("userRole").value,
      password: $("userPassword").value,
      active: $("userActive").value === "1",
    });
    toast("Login account saved.");
    $("userForm").reset();
    await loadUsers();
  } catch (e) {
    toast(e.message, true);
  }
};

let healthBusy = false;
async function checkLive() {
  if (!currentUser || healthBusy) return;
  healthBusy = true;
  try {
    const response = await fetch("/api/health", {
      cache: "no-store",
      signal: AbortSignal.timeout(6000),
    });
    const result = await response.json();
    if (!response.ok || !result.ok)
      throw Error(result.error || "Database unavailable");
    $("liveStatus").className = "liveStatus";
    $("liveLabel").textContent = "LIVE · CONNECTED";
    $("liveStatus").title =
      "Database write verified: " +
      stamp(result.checked_at) +
      " · Click to check again";
  } catch (e) {
    $("liveStatus").className = "liveStatus offline";
    $("liveLabel").textContent = "OFFLINE · CHECK CONNECTION";
    $("liveStatus").title = "Database write is not confirmed. Click to retry.";
  } finally {
    healthBusy = false;
  }
}
$("liveStatus").onclick = checkLive;
setInterval(checkLive, 5000);
window.addEventListener("offline", () => {
  $("liveStatus").className = "liveStatus offline";
  $("liveLabel").textContent = "OFFLINE · CHECK CONNECTION";
});
window.addEventListener("online", checkLive);

$("saveProfile").onclick = async () => {
  if (!selectedProfile) return;
  try {
    await api("/api/profile", {
      id: selectedProfile.id,
      version: selectedProfile.version,
      name: $("name").value,
      mobile: $("mobile").value,
      cnic: $("cnic").value,
      reason: $("profileReason").value,
    });
    const found = await api(
      "/api/search?" +
        new URLSearchParams({ q: $("mobile").value, mode: "phone" }),
    );
    const updated = found.find((v) => v.id === selectedProfile.id);
    if (updated) selectedProfile = updated;
    toast("Profile saved. Historical visits preserved.");
    $("profileReason").value = "";
    await load();
  } catch (e) {
    toast(e.message, true);
  }
};
function openEdit(v) {
  editRecord = v;
  for (let [id, key] of [
    ["editHost", "host"],
    ["editPurpose", "purpose"],
    ["editRemarks", "remarks"],
  ])
    $(id).value = v[key] || "";
  $("editReason").value = "";
  $("editPanel").hidden = false;
  $("editHost").focus();
  $("editPanel").scrollIntoView?.({ behavior: "smooth" });
}
$("cancelEdit").onclick = () => {
  $("editPanel").hidden = true;
  editRecord = null;
};
$("editVisitForm").onsubmit = async (e) => {
  e.preventDefault();
  if (!editRecord) return;
  const b = e.submitter || $("editVisitForm").querySelector(".primary");
  b.disabled = true;
  try {
    await api("/api/edit-visit", {
      id: editRecord.id,
      version: editRecord.version,
      host: $("editHost").value,
      purpose: $("editPurpose").value,
      remarks: $("editRemarks").value,
      reason: $("editReason").value,
    });
    $("editPanel").hidden = true;
    editRecord = null;
    toast("Visit correction saved with history.");
    await load();
  } catch (e) {
    toast(e.message, true);
  } finally {
    b.disabled = false;
  }
};
async function showChanges(entity, id) {
  try {
    let rows = await api("/api/changes?" + new URLSearchParams({ entity, id }));
    $("changeRows").replaceChildren();
    for (let r of rows) {
      let box = document.createElement("pre");
      box.textContent =
        stamp(r.at) +
        " · " +
        r.staff +
        " · " +
        r.action +
        "\nBefore: " +
        (r.before_json || "—") +
        "\nAfter: " +
        (r.after_json || "—");
      $("changeRows").append(box);
    }
    $("changePanel").hidden = false;
    $("changePanel").scrollIntoView?.({ behavior: "smooth" });
  } catch (e) {
    toast(e.message, true);
  }
}
$("closeChanges").onclick = () => ($("changePanel").hidden = true);
// Enter confirms the visitor form; textarea Enter remains available for multi-line remarks.
for (let id of ["mobile", "name", "cnic", "host"])
  $(id).addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      $("visitForm").requestSubmit();
    }
  });

$("togglePassword").onclick = () => {
  const show = $("password").type === "password";
  $("password").type = show ? "text" : "password";
  $("togglePassword").textContent = show ? "Hide" : "Show";
  $("togglePassword").setAttribute?.("aria-pressed", String(show));
  $("togglePassword").setAttribute?.(
    "aria-label",
    show ? "Hide password" : "Show password",
  );
};
$("focusVisitor").onclick = () => {
  $("mobile").focus();
  $("visitForm").scrollIntoView?.({ behavior: "smooth", block: "center" });
};
$("focusCall").onclick = () => {
  $("callPhone").focus();
  $("callForm").scrollIntoView?.({ behavior: "smooth", block: "center" });
};
$("refreshVisitors").onclick = load;
$("refreshCalls").onclick = loadCalls;
window.addEventListener("beforeunload", (e) => {
  if (callStart) {
    e.preventDefault();
    e.returnValue = "A call timer is running.";
  }
});
