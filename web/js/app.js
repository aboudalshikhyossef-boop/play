(function () {
  "use strict";

  var room = null;
  var player = null;
  var match = null;
  var pollTimer = null;
  var mutationBusy = false;
  var pollBusy = false;
  var requestSequence = 0;

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(node, value) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
    node.appendChild(document.createTextNode(value === null || value === undefined ? "" : String(value)));
  }

  function setTextById(id, value) {
    setText(byId(id), value);
  }

  function setNotice(id, value, state) {
    var node = byId(id);
    node.className = "notice" + (state ? " " + state : "");
    setText(node, value);
  }

  function show(element, visible) {
    var className = element.className.replace(/\s*hidden\b/g, "").replace(/^\s+|\s+$/g, "");
    element.className = visible ? className : className + " hidden";
  }

  function request(method, path, data, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, path, true);
    xhr.timeout = 10000;
    if (data !== null && data !== undefined) {
      xhr.setRequestHeader("Content-Type", "application/json; charset=UTF-8");
    }
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) {
        return;
      }
      var payload = {};
      try {
        payload = xhr.responseText ? JSON.parse(xhr.responseText) : {};
      } catch (error) {
        callback({ ok: false, error: "تعذر قراءة استجابة الخادم." }, xhr.status || 0);
        return;
      }
      callback(payload, xhr.status);
    };
    xhr.ontimeout = function () {
      callback({ ok: false, error: "انتهت مهلة الاتصال. حاول مرة أخرى." }, 0);
    };
    xhr.onerror = function () {
      callback({ ok: false, error: "انقطع الاتصال بالخادم. تحقق من الإنترنت." }, 0);
    };
    xhr.send(data === null || data === undefined ? null : JSON.stringify(data));
  }

  function setConnection(online) {
    var node = byId("connectionText");
    var pill = node.parentNode;
    if (online) {
      setText(node, "متصل بالخادم");
      pill.style.borderColor = "#315c4d";
      pill.style.color = "#a7dfc6";
      pill.style.backgroundColor = "#172b29";
    } else {
      setText(node, "الاتصال متوقف");
      pill.style.borderColor = "#814354";
      pill.style.color = "#f4c1ca";
      pill.style.backgroundColor = "#382330";
    }
  }

  function stopPolling() {
    if (pollTimer !== null) {
      window.clearTimeout(pollTimer);
      pollTimer = null;
    }
    pollBusy = false;
  }

  function scheduleRoomPoll() {
    stopPolling();
    if (room && !match) {
      pollTimer = window.setTimeout(refreshRoom, 1600);
    }
  }

  function scheduleMatchPoll() {
    stopPolling();
    if (match && match.status === "active") {
      pollTimer = window.setTimeout(refreshMatch, 1400);
    } else if (match && match.status === "finished") {
      pollTimer = window.setTimeout(refreshMatch, 4000);
    }
  }

  function showHome(message, state) {
    stopPolling();
    room = null;
    player = null;
    match = null;
    show(byId("homeScreen"), true);
    show(byId("lobbyScreen"), false);
    show(byId("gameScreen"), false);
    if (message) {
      setNotice("homeStatus", message, state || "");
    }
  }

  function showLobby() {
    match = null;
    show(byId("homeScreen"), false);
    show(byId("lobbyScreen"), true);
    show(byId("gameScreen"), false);
  }

  function showGame() {
    show(byId("homeScreen"), false);
    show(byId("lobbyScreen"), false);
    show(byId("gameScreen"), true);
  }

  function makeRequestId() {
    requestSequence += 1;
    return "chaos-" + String(new Date().getTime()) + "-" + String(requestSequence) + "-" + String(Math.floor(Math.random() * 1000000));
  }

  function updateRoomAddress(code) {
    var path = "/?room=" + encodeURIComponent(code);
    var fullLink = window.location.protocol + "//" + window.location.host + path;
    byId("inviteLink").value = fullLink;
    if (window.history && window.history.replaceState) {
      try {
        window.history.replaceState(null, "", path);
      } catch (ignore) {}
    }
  }

  function createSeat(p) {
    var wrapper = document.createElement("div");
    wrapper.className = "player-seat";

    var number = document.createElement("div");
    number.className = "seat-number seat-" + p.color;
    setText(number, p.seat);
    wrapper.appendChild(number);

    var copy = document.createElement("div");
    copy.className = "seat-copy";
    var name = document.createElement("div");
    name.className = "seat-name";
    setText(name, p.name + (player && p.id === player.id ? " (أنت)" : ""));
    copy.appendChild(name);
    var subtitle = document.createElement("div");
    subtitle.className = "seat-subtitle";
    setText(subtitle, p.avatar);
    copy.appendChild(subtitle);
    wrapper.appendChild(copy);

    var state = document.createElement("div");
    state.className = "seat-state";
    if (!p.connected) {
      state.className += " offline";
      setText(state, "غير متصل");
    } else if (p.ready) {
      state.className += " ready";
      setText(state, "✓ جاهز");
    } else {
      setText(state, "بانتظار الجاهزية");
    }
    wrapper.appendChild(state);
    return wrapper;
  }

  function renderRoom(nextRoom, playerId) {
    room = nextRoom;
    player = null;
    for (var i = 0; i < room.players.length; i += 1) {
      if (room.players[i].id === playerId) {
        player = room.players[i];
        break;
      }
    }

    showLobby();
    setTextById("roomCodeDisplay", room.code);
    updateRoomAddress(room.code);
    setTextById("playerCount", room.occupied + " / 4");

    var seats = byId("playerSeats");
    while (seats.firstChild) {
      seats.removeChild(seats.firstChild);
    }
    for (var seat = 1; seat <= 4; seat += 1) {
      var found = null;
      for (var p = 0; p < room.players.length; p += 1) {
        if (room.players[p].seat === seat) {
          found = room.players[p];
          break;
        }
      }
      if (found) {
        seats.appendChild(createSeat(found));
      } else {
        seats.appendChild(createSeat({
          seat: seat,
          id: "",
          name: "مقعد متاح",
          color: ["violet", "rose", "mint", "gold"][seat - 1],
          avatar: "يمكن أن ينضم لاعب رابع",
          ready: false,
          connected: false
        }));
      }
    }

    var readyButton = byId("readyButton");
    setText(readyButton, player && player.ready ? "إلغاء الاستعداد" : "أنا جاهز");
    readyButton.disabled = !player;

    var canStart = !!room.all_ready && room.occupied >= 3 && room.occupied <= 4;
    show(byId("startMatchButton"), canStart);
    setNotice(
      "lobbyNotice",
      canStart
        ? "اكتمل العدد المطلوب والجميع جاهز. يمكن لأي لاعب بدء المباراة."
        : "تبدأ المباراة عند استعداد 3 أو 4 لاعبين. اللاعبون الحاليون: " + room.occupied + " من 4.",
      canStart ? "good" : ""
    );
    setConnection(true);
  }

  function createRoom() {
    if (mutationBusy) {
      return;
    }
    mutationBusy = true;
    byId("createButton").disabled = true;
    setNotice("homeStatus", "جارٍ إنشاء الغرفة...", "");
    request("POST", "/api/rooms", { name: byId("createName").value }, function (payload, status) {
      mutationBusy = false;
      byId("createButton").disabled = false;
      if (status === 201 && payload.ok) {
        enterRoom(payload);
      } else {
        setNotice("homeStatus", payload.error || "تعذر إنشاء الغرفة.", "bad");
      }
    });
  }

  function joinRoom() {
    if (mutationBusy) {
      return;
    }
    var code = byId("roomCode").value.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
    if (!code) {
      setNotice("homeStatus", "أدخل رمز الغرفة أولًا.", "bad");
      return;
    }
    mutationBusy = true;
    byId("joinButton").disabled = true;
    setNotice("homeStatus", "جارٍ التحقق من الرمز وحجز المقعد...", "");
    request("POST", "/api/rooms/" + encodeURIComponent(code) + "/join", {
      name: byId("joinName").value
    }, function (payload, status) {
      mutationBusy = false;
      byId("joinButton").disabled = false;
      if (status === 201 && payload.ok) {
        enterRoom(payload);
      } else {
        setNotice("homeStatus", payload.error || "تعذر الانضمام إلى الغرفة.", "bad");
      }
    });
  }

  function enterRoom(payload) {
    if (!payload || !payload.ok || !payload.room) {
      showHome("لم تصل بيانات الغرفة بشكل صحيح.", "bad");
      return;
    }
    renderRoom(payload.room, payload.player_id);
    checkForMatch();
    scheduleRoomPoll();
  }

  function checkForMatch() {
    if (!room || !player) {
      return;
    }
    request("GET", "/api/rooms/" + encodeURIComponent(room.code) + "/match", null, function (payload, status) {
      if (status === 200 && payload.ok) {
        renderMatch(payload);
        scheduleMatchPoll();
      } else if (status === 404 || status === 409) {
        match = null;
        showLobby();
        scheduleRoomPoll();
      } else if (status === 401) {
        showHome("انتهت جلسة اللاعب. أدخل رمز الغرفة للانضمام مجددًا.", "bad");
      }
    });
  }

  function refreshRoom() {
    if (!room || pollBusy) {
      scheduleRoomPoll();
      return;
    }
    pollBusy = true;
    request("GET", "/api/rooms/" + encodeURIComponent(room.code), null, function (payload, status) {
      pollBusy = false;
      if (status === 200 && payload.ok) {
        renderRoom(payload.room, payload.room.you ? payload.room.you.id : "");
        scheduleRoomPoll();
      } else if (status === 401) {
        showHome("انتهت جلسة اللاعب. أدخل رمز الغرفة للانضمام مجددًا.", "bad");
      } else {
        setConnection(false);
        scheduleRoomPoll();
      }
    });
  }

  function toggleReady() {
    if (!room || !player || mutationBusy) {
      return;
    }
    mutationBusy = true;
    byId("readyButton").disabled = true;
    request("POST", "/api/rooms/" + encodeURIComponent(room.code) + "/ready", {
      ready: !player.ready
    }, function (payload, status) {
      mutationBusy = false;
      byId("readyButton").disabled = false;
      if (status === 200 && payload.ok) {
        renderRoom(payload.room, player.id);
      } else {
        setNotice("lobbyNotice", payload.error || "تعذر تحديث الاستعداد.", "bad");
      }
      scheduleRoomPoll();
    });
  }

  function startMatch() {
    if (!room || mutationBusy) {
      return;
    }
    mutationBusy = true;
    byId("startMatchButton").disabled = true;
    setNotice("lobbyNotice", "جارٍ بدء المباراة على الخادم...", "");
    request("POST", "/api/rooms/" + encodeURIComponent(room.code) + "/start", {}, function (payload, status) {
      mutationBusy = false;
      byId("startMatchButton").disabled = false;
      if ((status === 201 || status === 200) && payload.ok) {
        renderMatch(payload);
        scheduleMatchPoll();
      } else {
        setNotice("lobbyNotice", payload.error || "تعذر بدء المباراة.", "bad");
        scheduleRoomPoll();
      }
    });
  }

  function leaveRoom() {
    if (!room || mutationBusy) {
      return;
    }
    mutationBusy = true;
    byId("leaveButton").disabled = true;
    request("POST", "/api/rooms/" + encodeURIComponent(room.code) + "/leave", {}, function (payload, status) {
      mutationBusy = false;
      byId("leaveButton").disabled = false;
      if (status === 200 && payload.ok) {
        if (window.history && window.history.replaceState) {
          try {
            window.history.replaceState(null, "", "/");
          } catch (ignore) {}
        }
        showHome("غادرت الغرفة. يمكنك إنشاء غرفة أو الانضمام إلى غرفة أخرى.", "good");
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
    try {
      copied = document.execCommand("copy");
    } catch (ignore) {
      copied = false;
    }
    setNotice(
      "lobbyNotice",
      copied ? "تم نسخ رابط الدعوة. أرسله إلى بقية اللاعبين." : "حدد الرابط وانسخه يدويًا من الحقل.",
      copied ? "good" : ""
    );
  }

  function addOption(select, value, label) {
    var option = document.createElement("option");
    option.value = value;
    option.appendChild(document.createTextNode(label));
    select.appendChild(option);
  }

  function fillTargets(select, players, allowedIds, includePlaceholder) {
    while (select.firstChild) {
      select.removeChild(select.firstChild);
    }
    if (includePlaceholder) {
      addOption(select, "", "اختر لاعبًا");
    }
    for (var i = 0; i < players.length; i += 1) {
      if (player && players[i].id === player.id) {
        continue;
      }
      if (allowedIds && allowedIds.indexOf(players[i].id) === -1) {
        continue;
      }
      addOption(select, players[i].id, "المقعد " + players[i].seat + " — " + players[i].name);
    }
  }

  function addEvent(textValue, style) {
    var node = document.createElement("div");
    node.className = "event-item" + (style ? " " + style : "");
    setText(node, textValue);
    byId("roundEvents").appendChild(node);
  }

  function renderRoundResult(result) {
    var target = byId("roundEvents");
    while (target.firstChild) {
      target.removeChild(target.firstChild);
    }
    if (!result) {
      addEvent("لم تصل تفاصيل نتيجة الجولة بعد.", "");
      return;
    }

    var actions = result.actions || [];
    for (var i = 0; i < actions.length; i += 1) {
      var action = actions[i];
      var description = action.player_name + ": ";
      if (action.action === "steal") {
        description += "اختار سرقة " + action.target_name + ".";
      } else if (action.action === "guard") {
        description += "اختار الحماية.";
      } else if (action.action === "wager") {
        description += "راهن بـ " + action.amount + " عملات.";
      } else {
        description += "مرّر هذه الجولة.";
      }
      addEvent(description, "");
    }

    var thefts = result.thefts || [];
    for (var t = 0; t < thefts.length; t += 1) {
      addEvent(
        "نجحت السرقة! " + thefts[t].attacker_name + " أخذ " + thefts[t].amount + " من " + thefts[t].target_name + ".",
        "success"
      );
    }

    var blocked = result.blocked_attacks || [];
    for (var b = 0; b < blocked.length; b += 1) {
      var blockedText = blocked[b].reason === "guarded"
        ? "الحماية أوقفت محاولة " + blocked[b].attacker_name + " ضد " + blocked[b].target_name + "."
        : blocked[b].target_name + " لم تعد لديه عملات يمكن سرقتها.";
      addEvent(blockedText, "warning");
    }

    var wagers = result.wagers || [];
    for (var w = 0; w < wagers.length; w += 1) {
      addEvent(
        wagers[w].won
          ? wagers[w].player_name + " فاز بالمراهنة وربح " + wagers[w].delta + " عملات."
          : wagers[w].player_name + " خسر المراهنة وفقد " + Math.abs(wagers[w].delta) + " عملات.",
        wagers[w].won ? "success" : "warning"
      );
    }

    var revenge = result.revenge_results || [];
    for (var r = 0; r < revenge.length; r += 1) {
      if (revenge[r].success) {
        addEvent(revenge[r].player_name + " انتقم واسترد عملة من " + revenge[r].target_name + ".", "success");
      } else if (revenge[r].reason === "empty_target") {
        addEvent("لم ينجح الانتقام لأن رصيد اللاعب المستهدف أصبح صفرًا.", "warning");
      }
    }

    if (!target.firstChild) {
      addEvent("انتهت الجولة دون تغيّر في الأرصدة.", "");
    }
  }

  function renderRoster(players) {
    var roster = byId("matchRoster");
    while (roster.firstChild) {
      roster.removeChild(roster.firstChild);
    }
    for (var i = 0; i < players.length; i += 1) {
      var p = players[i];
      var row = document.createElement("div");
      row.className = "match-player";

      var number = document.createElement("div");
      number.className = "seat-number seat-" + p.color;
      setText(number, p.seat);
      row.appendChild(number);

      var copy = document.createElement("div");
      copy.className = "match-player-copy";
      var name = document.createElement("div");
      name.className = "match-player-name";
      setText(name, p.name + (player && p.id === player.id ? " (أنت)" : ""));
      copy.appendChild(name);
      var seat = document.createElement("div");
      seat.className = "match-player-seat";
      setText(seat, p.connected ? "متصل" : "انقطع الاتصال مؤقتًا");
      copy.appendChild(seat);
      row.appendChild(copy);

      var coins = document.createElement("div");
      coins.className = "match-coins";
      setText(coins, p.coins);
      var caption = document.createElement("span");
      caption.className = "match-coin-label";
      setText(caption, "عملة");
      coins.appendChild(caption);
      row.appendChild(coins);
      roster.appendChild(row);
    }
    setTextById("matchPlayerCount", players.length + " لاعبين");
  }

  function setActionControlsEnabled(enabled) {
    byId("actionTarget").disabled = !enabled;
    byId("wagerAmount").disabled = !enabled;
    byId("stealAction").disabled = !enabled;
    byId("guardAction").disabled = !enabled;
    byId("wagerAction").disabled = !enabled;
    byId("passAction").disabled = !enabled;
  }

  function renderFinal(state) {
    var ranking = state.ranking || [];
    var winner = ranking.length ? ranking[0] : null;
    setTextById("winnerName", winner ? winner.name : "لا يوجد فائز");
    var holder = byId("finalRanking");
    while (holder.firstChild) {
      holder.removeChild(holder.firstChild);
    }
    for (var i = 0; i < ranking.length; i += 1) {
      var row = document.createElement("div");
      row.className = "final-rank-row";
      var rank = document.createElement("strong");
      setText(rank, (i + 1) + ".");
      row.appendChild(rank);
      var name = document.createElement("span");
      name.className = "final-rank-name";
      setText(name, ranking[i].name);
      row.appendChild(name);
      var coins = document.createElement("span");
      coins.className = "final-rank-coins";
      setText(coins, ranking[i].coins + " عملة");
      row.appendChild(coins);
      holder.appendChild(row);
    }
  }

  function renderMatch(state) {
    match = state;
    showGame();
    setConnection(true);
    setTextById("roundCounter", "الجولة " + state.round + " / " + state.total_rounds);
    setTextById("timerValue", state.seconds_remaining);
    renderRoster(state.players || []);

    show(byId("actionPanel"), state.phase === "actions");
    show(byId("revengePanel"), state.phase === "revenge");
    show(byId("resultPanel"), state.phase === "result" || state.phase === "revenge");
    show(byId("finalPanel"), state.phase === "finished");

    if (state.phase === "actions") {
      setTextById("phaseTitle", "الاختيارات السرية");
      setTextById("phaseDescription", "تُكشف الحركات معًا بعد إرسال الجميع أو انتهاء الوقت.");
      fillTargets(byId("actionTarget"), state.players || [], null, true);
      var actionLocked = !!state.private.action_submitted;
      setActionControlsEnabled(!actionLocked);
      setNotice(
        "actionStatus",
        actionLocked
          ? "تم قفل اختيارك سرًا. انتظر بقية اللاعبين والكشف الجماعي."
          : "اختر حركة واحدة. السرقة لا تكلف عملات، والحماية تكلف عملة، والمراهنة بين 1 و3.",
        actionLocked ? "good" : ""
      );
      setNotice(
        "matchNotice",
        "تم تسجيل " + state.actions_submitted + " من " + state.action_total + " اختيارات سرية.",
        ""
      );
    } else if (state.phase === "revenge") {
      setTextById("phaseTitle", "نافذة الانتقام");
      setTextById("phaseDescription", "لا يمكن للانتقام أن يطلق سلسلة انتقام أخرى.");
      fillTargets(byId("revengeTarget"), state.players || [], state.private.revenge_targets || [], true);
      var eligible = state.private.revenge_targets && state.private.revenge_targets.length > 0;
      var revengeLocked = !!state.private.revenge_submitted || !eligible || state.private.revenge_charges <= 0;
      byId("revengeTarget").disabled = revengeLocked;
      byId("counterstrikeAction").disabled = revengeLocked;
      byId("skipRevengeAction").disabled = !!state.private.revenge_submitted || !eligible;
      setNotice(
        "revengeStatus",
        state.private.revenge_submitted
          ? "تم تسجيل قرارك. انتظر بقية اللاعبين."
          : !eligible
            ? "لم تتعرض لسرقة ناجحة هذه الجولة. انتظر انتهاء نافذة الانتقام."
            : state.private.revenge_charges <= 0
              ? "استخدمت فرصتي الانتقام المتاحتين لك."
              : "لديك " + state.private.revenge_charges + " فرص انتقام متبقية.",
        state.private.revenge_submitted ? "good" : ""
      );
      setNotice("matchNotice", "يختار المتضررون الانتقام أو تجاوز الفرصة.", "");
      renderRoundResult(state.result);
    } else if (state.phase === "result") {
      setTextById("phaseTitle", "انكشفت الأوراق");
      setTextById("phaseDescription", "تُحدّث الأرصدة تلقائيًا وتبدأ الجولة التالية بعد لحظات.");
      setTextById("resultTitle", "نتائج الجولة " + state.round);
      setNotice("matchNotice", "الجولة التالية تبدأ تلقائيًا بعد انتهاء عدّاد النتائج.", "good");
      renderRoundResult(state.result);
    } else if (state.phase === "finished") {
      setTextById("phaseTitle", "انتهت المباراة");
      setTextById("phaseDescription", "تم حسم الترتيب النهائي على الخادم.");
      setTextById("resultTitle", "النتائج النهائية");
      setNotice("matchNotice", "يمكنكم بدء مباراة جديدة من الغرفة نفسها.", "good");
      renderFinal(state);
      byId("rematchButton").disabled = false;
    }
  }

  function refreshMatch() {
    if (!room || pollBusy) {
      scheduleMatchPoll();
      return;
    }
    pollBusy = true;
    request("GET", "/api/rooms/" + encodeURIComponent(room.code) + "/match", null, function (payload, status) {
      pollBusy = false;
      if (status === 200 && payload.ok) {
        renderMatch(payload);
        scheduleMatchPoll();
      } else if (status === 401) {
        showHome("انتهت جلسة اللاعب. أدخل رمز الغرفة للانضمام مجددًا.", "bad");
      } else {
        setConnection(false);
        scheduleMatchPoll();
      }
    });
  }

  function submitMove(action, targetId, amount) {
    if (!room || mutationBusy || !match || match.phase !== "actions" || match.private.action_submitted) {
      return;
    }
    mutationBusy = true;
    setActionControlsEnabled(false);
    setNotice("actionStatus", "جارٍ تسجيل اختيارك السري...", "");
    request("POST", "/api/rooms/" + encodeURIComponent(room.code) + "/match/action", {
      request_id: makeRequestId(),
      action: action,
      target_player_id: targetId || null,
      amount: amount || 0
    }, function (payload, status) {
      mutationBusy = false;
      if (status === 200 && payload.ok) {
        renderMatch(payload);
      } else {
        setActionControlsEnabled(true);
        setNotice("actionStatus", payload.error || "تعذر تسجيل الحركة.", "bad");
      }
      scheduleMatchPoll();
    });
  }

  function submitRevenge(action, targetId) {
    if (!room || mutationBusy || !match || match.phase !== "revenge" || match.private.revenge_submitted) {
      return;
    }
    mutationBusy = true;
    byId("counterstrikeAction").disabled = true;
    byId("skipRevengeAction").disabled = true;
    request("POST", "/api/rooms/" + encodeURIComponent(room.code) + "/match/revenge", {
      request_id: makeRequestId(),
      action: action,
      target_player_id: targetId || null
    }, function (payload, status) {
      mutationBusy = false;
      if (status === 200 && payload.ok) {
        renderMatch(payload);
      } else {
        byId("counterstrikeAction").disabled = false;
        byId("skipRevengeAction").disabled = false;
        setNotice("revengeStatus", payload.error || "تعذر تسجيل قرار الانتقام.", "bad");
      }
      scheduleMatchPoll();
    });
  }

  function queryRoomCode() {
    var query = window.location.search || "";
    var parts = query.replace(/^\?/, "").split("&");
    for (var i = 0; i < parts.length; i += 1) {
      var pair = parts[i].split("=");
      if (decodeURIComponent(pair[0] || "") === "room") {
        try {
          return decodeURIComponent((pair[1] || "").replace(/\+/g, " ")).toUpperCase();
        } catch (ignore) {
          return "";
        }
      }
    }
    return "";
  }

  function boot() {
    var code = queryRoomCode();
    if (code) {
      byId("roomCode").value = code;
    }
    request("GET", "/api/me", null, function (payload, status) {
      if (status === 200 && payload.ok) {
        if (!code || code === payload.invite_code) {
          enterRoom(payload);
          return;
        }
        showHome("هذا المتصفح مسجل في غرفة أخرى. استخدم جلسة منفصلة للغرفة الجديدة.", "");
      } else {
        showHome(code ? "أدخل اسمك ثم انضم برمز الغرفة الموجود في الرابط." : "الاتصال بالخادم جاهز. أنشئ غرفة أو أدخل رمز دعوة.", "");
      }
      setConnection(true);
    });
  }

  byId("createButton").onclick = createRoom;
  byId("joinButton").onclick = joinRoom;
  byId("readyButton").onclick = toggleReady;
  byId("startMatchButton").onclick = startMatch;
  byId("leaveButton").onclick = leaveRoom;
  byId("copyButton").onclick = copyInvite;

  byId("stealAction").onclick = function () {
    var target = byId("actionTarget").value;
    if (!target) {
      setNotice("actionStatus", "اختر لاعبًا أولًا.", "bad");
      return;
    }
    submitMove("steal", target, 0);
  };
  byId("guardAction").onclick = function () {
    submitMove("guard", null, 0);
  };
  byId("wagerAction").onclick = function () {
    var amount = parseInt(byId("wagerAmount").value, 10);
    submitMove("wager", null, amount);
  };
  byId("passAction").onclick = function () {
    submitMove("pass", null, 0);
  };
  byId("counterstrikeAction").onclick = function () {
    var target = byId("revengeTarget").value;
    if (!target) {
      setNotice("revengeStatus", "لا يوجد هدف صالح للانتقام.", "bad");
      return;
    }
    submitRevenge("counterstrike", target);
  };
  byId("skipRevengeAction").onclick = function () {
    submitRevenge("pass", null);
  };
  byId("rematchButton").onclick = startMatch;
  byId("roomCode").onkeyup = function () {
    this.value = this.value.toUpperCase();
  };

  if (window.addEventListener) {
    window.addEventListener("online", function () {
      setConnection(true);
      if (match) {
        refreshMatch();
      } else if (room) {
        refreshRoom();
      }
    }, false);
    window.addEventListener("offline", function () {
      setConnection(false);
    }, false);
  }

  boot();
}());
