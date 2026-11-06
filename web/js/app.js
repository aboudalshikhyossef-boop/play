(function () {
  "use strict";

  var currentRoom = null;
  var currentPlayer = null;
  var pollTimer = null;
  var requestBusy = false;

  function byId(id) { return document.getElementById(id); }

  function text(element, value) {
    while (element.firstChild) { element.removeChild(element.firstChild); }
    element.appendChild(document.createTextNode(value === null || value === undefined ? "" : String(value)));
  }

  function setNotice(id, value, state) {
    var node = byId(id);
    node.className = "notice" + (state ? " " + state : "");
    text(node, value);
  }

  function setConnection(online) {
    var node = byId("connectionText");
    var pill = node.parentNode;
    if (online) {
      text(node, "متصل بالخادم");
      pill.style.borderColor = "#315c4d";
      pill.style.color = "#a7dfc6";
      pill.style.backgroundColor = "#172b29";
    } else {
      text(node, "الاتصال متوقف");
      pill.style.borderColor = "#814354";
      pill.style.color = "#f4c1ca";
      pill.style.backgroundColor = "#382330";
    }
  }

  function request(method, path, data, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, path, true);
    xhr.timeout = 9000;
    if (data !== null && data !== undefined) {
      xhr.setRequestHeader("Content-Type", "application/json; charset=UTF-8");
    }
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) { return; }
      var payload = {};
      try {
        payload = xhr.responseText ? JSON.parse(xhr.responseText) : {};
      } catch (error) {
        callback({ ok: false, error: "تعذر قراءة رد الخادم." }, xhr.status || 0);
        return;
      }
      callback(payload, xhr.status);
    };
    xhr.ontimeout = function () {
      callback({ ok: false, error: "انتهت مهلة الاتصال. تحقق من الإنترنت ثم حاول مجددًا." }, 0);
    };
    xhr.onerror = function () {
      callback({ ok: false, error: "تعذر الوصول إلى الخادم. قد يكون الاتصال انقطع مؤقتًا." }, 0);
    };
    xhr.send(data === null || data === undefined ? null : JSON.stringify(data));
  }

  function showHome(message, state) {
    stopPolling();
    currentRoom = null;
    currentPlayer = null;
    byId("homeScreen").className = "screen";
    byId("lobbyScreen").className = "screen hidden";
    if (message) { setNotice("homeStatus", message, state || ""); }
  }

  function updateRoomAddress(code) {
    var path = "/?room=" + encodeURIComponent(code);
    var fullLink = window.location.protocol + "//" + window.location.host + path;
    byId("inviteLink").value = fullLink;
    if (window.history && window.history.replaceState) {
      try { window.history.replaceState(null, "", path); } catch (ignore) {}
    }
  }

  function createSeat(player) {
    var wrapper = document.createElement("div");
    wrapper.className = "player-seat";

    var number = document.createElement("div");
    number.className = "seat-number seat-" + player.color;
    text(number, player.seat);
    wrapper.appendChild(number);

    var copy = document.createElement("div");
    copy.className = "seat-copy";
    var name = document.createElement("div");
    name.className = "seat-name";
    text(name, player.name + (currentPlayer && player.id === currentPlayer.id ? " (أنت)" : ""));
    copy.appendChild(name);
    var subtitle = document.createElement("div");
    subtitle.className = "seat-subtitle";
    text(subtitle, player.avatar);
    copy.appendChild(subtitle);
    wrapper.appendChild(copy);

    var state = document.createElement("div");
    state.className = "seat-state";
    if (!player.connected) {
      state.className += " offline";
      text(state, "غير متصل");
    } else if (player.ready) {
      state.className += " ready";
      text(state, "✓ جاهز");
    } else {
      text(state, "بانتظار الجاهزية");
    }
    wrapper.appendChild(state);
    return wrapper;
  }

  function renderRoom(room, playerId) {
    currentRoom = room;
    currentPlayer = null;
    for (var i = 0; i < room.players.length; i += 1) {
      if (room.players[i].id === playerId) {
        currentPlayer = room.players[i];
        break;
      }
    }

    byId("homeScreen").className = "screen hidden";
    byId("lobbyScreen").className = "screen";
    text(byId("roomCodeDisplay"), room.code);
    updateRoomAddress(room.code);
    text(byId("playerCount"), room.occupied + " / 4");

    var seats = byId("playerSeats");
    while (seats.firstChild) { seats.removeChild(seats.firstChild); }
    for (var seat = 1; seat <= 4; seat += 1) {
      var found = null;
      for (var p = 0; p < room.players.length; p += 1) {
        if (room.players[p].seat === seat) { found = room.players[p]; break; }
      }
      if (found) {
        seats.appendChild(createSeat(found));
      } else {
        seats.appendChild(createSeat({
          seat: seat,
          id: "",
          name: "مقعد شاغر",
          color: ["violet", "rose", "mint", "gold"][seat - 1],
          avatar: "بانتظار لاعب",
          ready: false,
          connected: false
        }));
      }
    }

    var readyButton = byId("readyButton");
    text(readyButton, currentPlayer && currentPlayer.ready ? "إلغاء الاستعداد" : "أنا جاهز");
    readyButton.disabled = !currentPlayer;

    if (room.all_ready) {
      setNotice("lobbyNotice", "اكتمل اللاعبون الأربعة والجميع جاهز. ستبدأ المباراة بعد اكتمال محرك الجولات.", "good");
    } else if (room.occupied < 4) {
      setNotice("lobbyNotice", "بانتظار " + (4 - room.occupied) + " لاعب(ين) للانضمام إلى الغرفة.", "");
    } else {
      setNotice("lobbyNotice", "اكتمل عدد اللاعبين. بانتظار استعداد الجميع.", "");
    }
    setConnection(true);
  }

  function refreshRoom() {
    if (!currentRoom || requestBusy) { schedulePoll(); return; }
    requestBusy = true;
    request("GET", "/api/rooms/" + encodeURIComponent(currentRoom.code), null, function (payload, status) {
      requestBusy = false;
      if (status === 200 && payload.ok) {
        renderRoom(payload.room, currentPlayer ? currentPlayer.id : "");
      } else if (status === 401) {
        showHome("انتهت جلسة اللاعب. أدخل رمز الغرفة للانضمام من جديد.", "bad");
      } else {
        setConnection(false);
      }
      schedulePoll();
    });
  }

  function schedulePoll() {
    stopPolling();
    if (currentRoom) { pollTimer = window.setTimeout(refreshRoom, 1600); }
  }

  function stopPolling() {
    if (pollTimer !== null) {
      window.clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  function enterRoom(payload) {
    if (!payload || !payload.ok || !payload.room) {
      showHome("لم تصل بيانات الغرفة بشكل صحيح.", "bad");
      return;
    }
    renderRoom(payload.room, payload.player_id);
    schedulePoll();
  }

  function createRoom() {
    if (requestBusy) { return; }
    var name = byId("createName").value;
    requestBusy = true;
    byId("createButton").disabled = true;
    setNotice("homeStatus", "جارٍ إنشاء الغرفة على الخادم...", "");
    request("POST", "/api/rooms", { name: name }, function (payload, status) {
      requestBusy = false;
      byId("createButton").disabled = false;
      if (status === 201 && payload.ok) {
        enterRoom(payload);
      } else {
        setNotice("homeStatus", payload.error || "تعذر إنشاء الغرفة.", "bad");
      }
    });
  }

  function joinRoom() {
    if (requestBusy) { return; }
    var name = byId("joinName").value;
    var code = byId("roomCode").value.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
    if (!code) {
      setNotice("homeStatus", "أدخل رمز الغرفة أولًا.", "bad");
      return;
    }
    requestBusy = true;
    byId("joinButton").disabled = true;
    setNotice("homeStatus", "جارٍ التحقق من رمز الغرفة وحجز المقعد...", "");
    request("POST", "/api/rooms/" + encodeURIComponent(code) + "/join", { name: name }, function (payload, status) {
      requestBusy = false;
      byId("joinButton").disabled = false;
      if (status === 201 && payload.ok) {
        enterRoom(payload);
      } else {
        setNotice("homeStatus", payload.error || "تعذر الانضمام إلى الغرفة.", "bad");
      }
    });
  }

  function toggleReady() {
    if (!currentRoom || !currentPlayer || requestBusy) { return; }
    requestBusy = true;
    byId("readyButton").disabled = true;
    request("POST", "/api/rooms/" + encodeURIComponent(currentRoom.code) + "/ready", {
      ready: !currentPlayer.ready
    }, function (payload, status) {
      requestBusy = false;
      byId("readyButton").disabled = false;
      if (status === 200 && payload.ok) {
        renderRoom(payload.room, currentPlayer.id);
      } else {
        setNotice("lobbyNotice", payload.error || "تعذر تحديث حالة الاستعداد.", "bad");
      }
      schedulePoll();
    });
  }

  function leaveRoom() {
    if (!currentRoom || requestBusy) { return; }
    var code = currentRoom.code;
    requestBusy = true;
    byId("leaveButton").disabled = true;
    request("POST", "/api/rooms/" + encodeURIComponent(code) + "/leave", {}, function (payload, status) {
      requestBusy = false;
      byId("leaveButton").disabled = false;
      if (status === 200 && payload.ok) {
        if (window.history && window.history.replaceState) {
          try { window.history.replaceState(null, "", "/"); } catch (ignore) {}
        }
        showHome("غادرت الغرفة. يمكنك إنشاء غرفة أخرى أو الانضمام إلى غرفة جديدة.", "good");
      } else {
        setNotice("lobbyNotice", payload.error || "تعذرت مغادرة الغرفة.", "bad");
      }
    });
  }

  function copyInvite() {
    var input = byId("inviteLink");
    input.focus();
    input.select();
    var copied = false;
    try { copied = document.execCommand("copy"); } catch (ignore) { copied = false; }
    if (copied) {
      setNotice("lobbyNotice", "تم نسخ رابط الدعوة. أرسله إلى اللاعبين الثلاثة.", "good");
    } else {
      setNotice("lobbyNotice", "حدد الرابط وانسخه يدويًا من الحقل.", "");
    }
  }

  function queryRoomCode() {
    var query = window.location.search || "";
    var parts = query.replace(/^\?/, "").split("&");
    for (var i = 0; i < parts.length; i += 1) {
      var pair = parts[i].split("=");
      if (decodeURIComponent(pair[0] || "") === "room") {
        try { return decodeURIComponent((pair[1] || "").replace(/\+/g, " ")).toUpperCase(); }
        catch (ignore) { return ""; }
      }
    }
    return "";
  }

  function boot() {
    var code = queryRoomCode();
    if (code) { byId("roomCode").value = code; }
    request("GET", "/api/me", null, function (payload, status) {
      if (status === 200 && payload.ok) {
        if (!code || code === payload.invite_code) {
          enterRoom(payload);
          return;
        }
        showHome("هذا المتصفح مسجل في غرفة أخرى. أدخل اسمك للانضمام إلى الغرفة الموجودة في الرابط.", "");
      } else {
        showHome(code ? "أدخل اسمك ثم انضم باستخدام رمز الغرفة الموجود في الرابط." : "الاتصال بالخادم جاهز. أنشئ غرفة أو أدخل رمز دعوة.", "");
      }
      setConnection(true);
    });
  }

  byId("createButton").onclick = createRoom;
  byId("joinButton").onclick = joinRoom;
  byId("readyButton").onclick = toggleReady;
  byId("leaveButton").onclick = leaveRoom;
  byId("copyButton").onclick = copyInvite;
  byId("roomCode").onkeyup = function () { this.value = this.value.toUpperCase(); };

  if (window.addEventListener) {
    window.addEventListener("online", function () { setConnection(true); if (currentRoom) { refreshRoom(); } }, false);
    window.addEventListener("offline", function () { setConnection(false); }, false);
  }

  boot();
}());
