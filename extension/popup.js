document.getElementById("save").onclick = async () => {
  const token = document.getElementById("token").value;
  const apiUrl = document.getElementById("apiUrl").value;
  await chrome.storage.local.set({ dorvey_token: token, dorvey_api: apiUrl || "http://localhost:8000" });
  document.getElementById("status").textContent = "Saved.";
  setTimeout(() => document.getElementById("status").textContent = "", 2000);
};

chrome.storage.local.get(["dorvey_token", "dorvey_api"], (r) => {
  if (r.dorvey_token) document.getElementById("token").value = r.dorvey_token;
  if (r.dorvey_api) document.getElementById("apiUrl").value = r.dorvey_api;
});
