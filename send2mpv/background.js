// 封裝建立通知的函式
function showNotification(title, message, isError = false) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icon.png", // 使用你剛設定的 icon
    title: title,
    message: message,
    priority: isError ? 2 : 0 // 錯誤時提高優先級
  });
}

chrome.action.onClicked.addListener((tab) => {
  const targetIp = "10.144.1.98";
  const targetPort = "9998";
  const url = tab.url;

  console.log("準備傳送:", url);

  fetch(`http://${targetIp}:${targetPort}/mpv`, {
    method: "POST",
    mode: "no-cors", 
    body: JSON.stringify({ command: ["loadfile", url] })
  })
  .then(() => {
    // 方法一：成功時也跳通知（非必須，看你喜歡）
    //showNotification("✅ 傳送成功", `已將網址送至 MPV。`);
    console.log("傳送成功");
  })
  .catch((error) => {
    // 🔴 關鍵部分：失敗時跳出紅色警告通知
    showNotification(
      "❌ 傳送失敗", 
      `無法連線到 ${targetIp}:${targetPort}。\n請檢查 Linux 上的 ai_window.py 是否執行中，或防火牆是否開啟。`,
      true
    );
    console.error("傳送失敗:", error);
  });
});