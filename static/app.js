// Contacts app frontend: plain JavaScript, no framework.
//
// How it fits together:
//   * The URL hash says what's on screen: "#/contacts/5" shows contact 5,
//     "#/new" shows a blank form, and no hash shows the empty state. Because
//     the sidebar entries are ordinary links, refreshing, bookmarking and the
//     Back button all just work. route() reads the hash and updates the page.
//   * api() wraps fetch() for talking to the Flask REST API.
//   * "Dirty" means the form has unsaved changes. We record a snapshot of the
//     form when a contact loads and compare against it.

"use strict";

// Same pattern as EMAIL_RE in app.py, so browser and server agree.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// ---- Page elements ---------------------------------------------------------

const $ = (selector) => document.querySelector(selector);

const els = {
  list: $("#contact-list"),
  listMessage: $("#list-message"),
  search: $("#search"),
  newButton: $("#new-contact"),
  emptyState: $("#empty-state"),
  form: $("#contact-form"),
  firstName: $("#first-name"),
  lastName: $("#last-name"),
  emailList: $("#email-list"),
  emailTemplate: $("#email-row-template"),
  addEmail: $("#add-email"),
  deleteButton: $("#delete"),
  cancelButton: $("#cancel"),
  saveButton: $("#save"),
  toast: $("#toast"),
};

// ---- State -----------------------------------------------------------------

const state = {
  contacts: [],       // every contact, as returned by GET /api/contacts
  current: null,      // the saved contact being edited (null for a new one)
  isNew: false,       // true while filling in the "#/new" form
  snapshot: null,     // form contents at the last load/save, for isDirty()
  busy: false,        // true while a save/delete request is in flight
  hash: location.hash // the hash we're currently showing
};

// ---- API helper ------------------------------------------------------------

class ApiError extends Error {
  constructor(message, status, fields) {
    super(message);
    this.status = status;
    this.fields = fields || {};
  }
}

async function api(method, url, body) {
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    // fetch() only throws when the request couldn't be sent at all.
    throw new ApiError("Couldn't reach the server. Check your connection and try again.", 0);
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(data?.error || `Request failed (${response.status}).`, response.status, data?.fields);
  }
  return data;
}

// ---- Sidebar ---------------------------------------------------------------

async function loadList() {
  try {
    state.contacts = await api("GET", "/api/contacts");
  } catch (err) {
    showToast(err.message, true);
  }
  renderList();
}

function fullName(contact) {
  return `${contact.first_name} ${contact.last_name}`;
}

function renderList() {
  const query = els.search.value.trim().toLowerCase();
  const matches = state.contacts.filter((c) =>
    !query ||
    fullName(c).toLowerCase().includes(query) ||
    c.emails.some((e) => e.toLowerCase().includes(query))
  );

  els.list.replaceChildren(
    ...matches.map((contact) => {
      const link = document.createElement("a");
      link.href = `#/contacts/${contact.id}`;
      // Always use textContent (never innerHTML) for user data. Otherwise a
      // contact named <img src=x onerror=...> could run code in the page (XSS).
      link.textContent = fullName(contact);
      link.title = fullName(contact);
      if (state.current && state.current.id === contact.id) {
        link.classList.add("selected");
        link.setAttribute("aria-current", "true");
      }
      const item = document.createElement("li");
      item.append(link);
      return item;
    })
  );

  if (state.contacts.length === 0) {
    showListMessage("No contacts yet.");
  } else if (matches.length === 0) {
    showListMessage("No matching contacts.");
  } else {
    showListMessage(null);
  }

  els.list.querySelector(".selected")?.scrollIntoView({ block: "nearest" });
}

function showListMessage(text) {
  els.listMessage.hidden = !text;
  els.listMessage.textContent = text || "";
}

// ---- Routing ---------------------------------------------------------------

// Bumped on each navigation, so a slow response for a contact the user has
// already clicked away from gets ignored instead of overwriting the form.
let routeToken = 0;

// The last contact opened, so cancelling a new contact can go back to it.
let previousContactHash = null;

async function route() {
  if (/^#\/contacts\/\d+$/.test(state.hash)) previousContactHash = state.hash;
  state.hash = location.hash;
  const token = ++routeToken;
  const match = location.hash.match(/^#\/contacts\/(\d+)$/);

  if (location.hash === "#/new") {
    showForm(null);
  } else if (match) {
    try {
      const contact = await api("GET", `/api/contacts/${match[1]}`);
      if (token === routeToken) showForm(contact);
    } catch (err) {
      if (token !== routeToken) return;
      showToast(err.status === 404 ? "That contact no longer exists." : err.message, true);
      if (err.status === 404) {
        loadList(); // someone may have deleted it in another tab
        goTo("", { replace: true });
      }
    }
  } else {
    showEmpty();
  }
}

// Navigate somewhere in the app. With replace, the current history entry is
// overwritten (so Back won't return to, e.g., an empty "new contact" form).
function goTo(hash, { replace = false } = {}) {
  if (replace) {
    history.replaceState(null, "", hash || location.pathname);
    route();
  } else {
    location.hash = hash; // fires "hashchange", which calls route()
  }
}

window.addEventListener("hashchange", () => {
  if (isDirty() && !confirm("You have unsaved changes. Discard them?")) {
    // Stay put: quietly put the previous hash back.
    history.replaceState(null, "", state.hash || location.pathname);
    return;
  }
  route();
});

// Warn before closing or reloading the tab with unsaved changes.
window.addEventListener("beforeunload", (event) => {
  if (isDirty()) event.preventDefault();
});

// ---- Form ------------------------------------------------------------------

function showEmpty() {
  state.current = null;
  state.isNew = false;
  state.snapshot = null;
  els.form.hidden = true;
  els.emptyState.hidden = false;
  renderList();
}

// Fill the form with a contact, or blank it for a new one (contact = null).
function showForm(contact) {
  state.current = contact;
  state.isNew = !contact;

  els.firstName.value = contact?.first_name ?? "";
  els.lastName.value = contact?.last_name ?? "";
  els.emailList.replaceChildren();
  const emails = contact ? contact.emails : [""]; // new contacts start with one blank email
  emails.forEach((email) => addEmailRow(email));

  clearErrors();
  els.deleteButton.hidden = state.isNew; // nothing to delete until it's saved
  els.emptyState.hidden = true;
  els.form.hidden = false;

  state.snapshot = serializeForm();
  updateButtons();
  renderList();

  if (state.isNew) els.firstName.focus();
}

function addEmailRow(value = "") {
  const row = els.emailTemplate.content.firstElementChild.cloneNode(true);
  row.querySelector(".email-input").value = value;
  els.emailList.append(row);
  return row;
}

function emailInputs() {
  return [...els.emailList.querySelectorAll(".email-input")];
}

// The form's contents in the shape the API expects. Blank email rows are
// sent too, so the server's "emails.<index>" errors line up with the rows
// on screen (the server skips blanks).
function formData() {
  return {
    first_name: els.firstName.value.trim(),
    last_name: els.lastName.value.trim(),
    emails: emailInputs().map((input) => input.value.trim()),
  };
}

// A comparable string of the form, ignoring blank email rows, so clicking
// "add email" without typing anything doesn't count as a change.
function serializeForm() {
  const data = formData();
  data.emails = data.emails.filter(Boolean);
  return JSON.stringify(data);
}

function isDirty() {
  return state.snapshot !== null && serializeForm() !== state.snapshot;
}

function updateButtons() {
  els.saveButton.disabled = state.busy || !isDirty();
  // Cancel stays enabled even with no changes: it also tidies away blank
  // email rows, which don't count as changes.
  els.cancelButton.disabled = state.busy;
  els.deleteButton.disabled = state.busy;
}

// ---- Validation ------------------------------------------------------------

// Returns an errors object shaped like the server's, e.g.
// { first_name: "...", "emails.2": "..." }. Empty means valid.
function validate(data) {
  const errors = {};
  if (!data.first_name) errors.first_name = "First name is required.";
  if (!data.last_name) errors.last_name = "Last name is required.";

  const seen = new Set();
  data.emails.forEach((email, i) => {
    if (!email) return;
    const key = email.toLowerCase();
    if (!EMAIL_RE.test(email)) {
      errors[`emails.${i}`] = `"${email}" is not a valid email address.`;
    } else if (seen.has(key)) {
      errors[`emails.${i}`] = "This email is already listed for this contact.";
    }
    seen.add(key);
  });
  return errors;
}

function clearErrors() {
  els.form.querySelectorAll(".error").forEach((p) => (p.textContent = ""));
  els.form.querySelectorAll(".invalid").forEach((input) => {
    input.classList.remove("invalid");
    input.removeAttribute("aria-invalid");
  });
}

function showErrors(errors) {
  clearErrors();
  let firstInvalid = null;

  for (const [field, message] of Object.entries(errors)) {
    let input, messageEl;
    const emailMatch = field.match(/^emails\.(\d+)$/);
    if (emailMatch) {
      const row = els.emailList.children[Number(emailMatch[1])];
      input = row?.querySelector(".email-input");
      messageEl = row?.querySelector(".error");
    } else {
      input = els.form.querySelector(`[name="${field}"]`);
      messageEl = els.form.querySelector(`[data-error-for="${field}"]`);
    }
    if (messageEl) messageEl.textContent = message;
    if (input) {
      input.classList.add("invalid");
      input.setAttribute("aria-invalid", "true");
      firstInvalid ??= input;
    }
  }
  firstInvalid?.focus();
}

// Clear a field's error as soon as the user starts fixing it.
function clearFieldError(input) {
  if (!input.classList.contains("invalid")) return;
  input.classList.remove("invalid");
  input.removeAttribute("aria-invalid");
  const messageEl = input.closest(".email-row")?.querySelector(".error") ||
    els.form.querySelector(`[data-error-for="${input.name}"]`);
  if (messageEl) messageEl.textContent = "";
}

// ---- Actions ---------------------------------------------------------------

async function save() {
  if (state.busy || !isDirty()) return;
  const data = formData();
  const errors = validate(data);
  if (Object.keys(errors).length) {
    showErrors(errors);
    return;
  }

  setBusy(true);
  try {
    const saved = state.isNew
      ? await api("POST", "/api/contacts", data)
      : await api("PUT", `/api/contacts/${state.current.id}`, data);
    state.snapshot = null; // so the navigation below doesn't ask about unsaved changes
    showToast(state.isNew ? "Contact created." : "Changes saved.");
    await loadList();
    goTo(`#/contacts/${saved.id}`, { replace: true });
  } catch (err) {
    if (err.status === 400 && Object.keys(err.fields).length) {
      showErrors(err.fields);
    } else {
      showToast(err.message, true);
      if (err.status === 404) loadList(); // it was deleted elsewhere
    }
  } finally {
    setBusy(false);
  }
}

function cancel() {
  if (state.isNew) {
    state.snapshot = null; // discard without asking
    // Go back to whichever contact was open before "+", if there was one.
    goTo(previousContactHash || "", { replace: true });
  } else if (state.current) {
    showForm(state.current); // put back the last saved values
  }
}

async function deleteContact() {
  if (state.busy || !state.current) return;
  const name = fullName(state.current);
  if (!confirm(`Delete ${name}? This can't be undone.`)) return;

  setBusy(true);
  try {
    await api("DELETE", `/api/contacts/${state.current.id}`);
    showToast(`${name} deleted.`);
  } catch (err) {
    // A 404 means it's already gone, which is what the user wanted anyway.
    if (err.status !== 404) {
      showToast(err.message, true);
      setBusy(false);
      return;
    }
  }
  setBusy(false);
  state.snapshot = null;
  state.hash = "";
  previousContactHash = null;
  await loadList();
  goTo("", { replace: true });
}

function setBusy(busy) {
  state.busy = busy;
  updateButtons();
}

let toastTimer;
function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle("error", isError);
  els.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (els.toast.hidden = true), isError ? 6000 : 3000);
}

// ---- Event listeners -------------------------------------------------------

els.newButton.addEventListener("click", () => goTo("#/new"));
els.search.addEventListener("input", renderList);

els.form.addEventListener("submit", (event) => {
  event.preventDefault(); // stop the browser's default full-page form submit
  save();
});

// One "input" listener on the whole form catches typing in any field,
// including email rows added later ("event delegation").
els.form.addEventListener("input", (event) => {
  clearFieldError(event.target);
  updateButtons();
});

els.addEmail.addEventListener("click", () => {
  addEmailRow().querySelector(".email-input").focus();
});

els.emailList.addEventListener("click", (event) => {
  const removeButton = event.target.closest(".remove");
  if (!removeButton) return;
  const row = removeButton.closest(".email-row");
  // Move keyboard focus somewhere sensible before the row disappears.
  const next = row.nextElementSibling || row.previousElementSibling;
  row.remove();
  (next?.querySelector(".email-input") || els.addEmail).focus();
  updateButtons();
});

els.cancelButton.addEventListener("click", cancel);
els.deleteButton.addEventListener("click", deleteContact);

// Ctrl+S / Cmd+S saves instead of opening the browser's "Save page" dialog.
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && !els.form.hidden) {
    event.preventDefault();
    save();
  }
});

// ---- Start -----------------------------------------------------------------

loadList();
route();
