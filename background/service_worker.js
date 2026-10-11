// background/service_worker.js - Manages extension lifecycle & full-tab replacement
"use strict";

chrome.runtime.onInstalled.addListener(() => {
  console.log("Local LLM Monitor extension installed.");
  // Disable automatic sidepanel opening on action click so that
  // chrome.action.onClicked triggers the Tab Replacement navigation to dashboard.html
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false })
      .catch((err) => console.warn("Could not set side panel behavior:", err));
  }
});

// Approach B: Tab Replacement (chrome.tabs.update)
// Hijacks the active tab's URL and redirects it straight to dashboard.html bundled inside extension
chrome.action.onClicked.addListener(async (tab) => {
  const targetUrl = chrome.runtime.getURL("dashboard.html");
  if (tab && tab.id) {
    try {
      await chrome.tabs.update(tab.id, { url: targetUrl });
    } catch (err) {
      console.warn("Failed to update active tab, creating new tab instead:", err);
      chrome.tabs.create({ url: targetUrl });
    }
  } else {
    chrome.tabs.create({ url: targetUrl });
  }
});
