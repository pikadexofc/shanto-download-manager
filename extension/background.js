/**
 * Shanto Download Manager (SDM) Chrome Interceptor
 * Intercepts native downloads and forwards headers/cookies to SDM Turbo Core
 */

const SDM_API = "http://127.0.0.1:48912/api/tasks";
let interceptionEnabled = true;

// Intercept browser downloads
chrome.downloads.onDeterminingFilename.addListener((downloadItem, suggest) => {
  if (!interceptionEnabled) return;

  // Avoid intercepting blob or data URLs
  if (downloadItem.url.startsWith("blob:") || downloadItem.url.startsWith("data:")) {
    return;
  }

  // Cancel native single-thread browser download
  chrome.downloads.cancel(downloadItem.id, () => {
    chrome.downloads.erase({ id: downloadItem.id });
  });

  // Extract cookies for authenticated downloads
  chrome.cookies.getAll({ url: downloadItem.url }, (cookies) => {
    const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
    const headers = {
      "User-Agent": navigator.userAgent,
      "Referer": downloadItem.referrer || "",
    };
    if (cookieHeader) {
      headers["Cookie"] = cookieHeader;
    }

    // Forward to SDM API
    fetch(SDM_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: downloadItem.url,
        filename: downloadItem.filename,
        headers: headers,
        auto_start: true,
      }),
    }).catch((err) => {
      console.error("[SDM Ext] Failed to dispatch download to SDM daemon", err);
    });
  });
});

// Context Menu: "Download with Shanto Download Manager"
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "sdm_download_link",
    title: "Download with Shanto Download Manager (Turbo)",
    contexts: ["link", "video", "audio", "image"],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  const targetUrl = info.linkUrl || info.srcUrl;
  if (!targetUrl) return;

  chrome.cookies.getAll({ url: targetUrl }, (cookies) => {
    const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
    const headers = {
      "User-Agent": navigator.userAgent,
      "Referer": tab ? tab.url : "",
    };
    if (cookieHeader) {
      headers["Cookie"] = cookieHeader;
    }

    fetch(SDM_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: targetUrl,
        headers: headers,
        auto_start: true,
      }),
    }).catch((err) => {
      console.error("[SDM Ext] Context menu dispatch error", err);
    });
  });
});
