// 封裝通知函式
function showNotification(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icon.png",
    title: title,
    message: message
  });
}

chrome.action.onClicked.addListener(async (tab) => {
  const url = tab.url;

  // 1. 嚴格檢查：只允許 YouTube 影片網址
  const isYouTube = url.includes("youtube.com/watch") || url.includes("youtu.be/");

  if (!isYouTube) {
    // 如果不是 YouTube，直接結束，什麼都不做
    // 你也可以選擇不跳通知，讓它按下去完全沒反應
	showNotification("Error", "非 YouTube 網址，目前不傳送");
    //console.log("非 YouTube 網址，忽略執行傳送。");
    return; 
  }

  // 2. 確定是 YouTube 後，嘗試暫停本地播放
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const video = document.querySelector('video');
        if (video) video.pause();
      }
    });
  } catch (e) {
    console.log("暫停失敗:", e);
  }

  // 3. 執行傳送邏輯
  const targetIp = "10.144.1.98";
  const targetPort = "9998";

  fetch(`http://${targetIp}:${targetPort}/mpv`, {
    method: "POST",
    mode: "no-cors",
    body: JSON.stringify({ command: ["loadfile", url] })
  })
  .then(() => {
    //showNotification("✅ 已傳送至 MPV", "影片已於遠端開啟並暫停本地播放。");
  })
  .catch((err) => {
    showNotification("❌ 傳送失敗", "無法連線到遠端伺服器。");
  });
});