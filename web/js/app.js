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
        checkForMatch();
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
    var isRematch = !!(match && match.status === "finished");
    var button = isRematch ? byId("rematchButton") : byId("startMatchButton");
    var noticeId = isRematch ? "matchNotice" : "lobbyNotice";

    mutationBusy = true;
    button.disabled = true;
    setNotice(noticeId, isRematch ? "جارٍ إنشاء مباراة جديدة..." : "جارٍ بدء المباراة على الخادم...", "");
    request("POST", "/api/rooms/" + encodeURIComponent(room.code) + "/start", {}, function (payload, status) {
      mutationBusy = false;
      button.disabled = false;
      if ((status === 201 || status === 200) && payload.ok) {
        renderMatch(payload);
        scheduleMatchPoll();
      } else {
        setNotice(noticeId, payload.error || "تعذر بدء المباراة.", "bad");
        if (isRematch) {
          scheduleMatchPoll();
        } else {
          scheduleRoomPoll();
        }
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
    var previousValue = select.value;
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
    if (previousValue) {
      var canRestore = false;
      for (var optionIndex = 0; optionIndex < select.options.length; optionIndex += 1) {
        if (select.options[optionIndex].value === previousValue) {
          canRestore = true;
          break;
        }
      }
      select.value = canRestore ? previousValue : "";
    }
  }

  function addEvent(textValue, style) {
    var node = document.createElement("div");
    node.className = "event-item" + (style ? " " + style : "");
    setText(node, textValue);
    byId("roundEvents").appendChild(node);
  }

  function renderChallenge(challenge, result, state) {
    var panel = byId("challengePanel");
    var summary = byId("challengeSummary");
    var active = state.phase === "challenge";
    var answerSelect = byId("challengeAnswer");
    var submitButton = byId("challengeSubmit");
    show(panel, active);
    show(summary, !!result && !active);

    if (challenge) {
      if (answerSelect.getAttribute("data-challenge-id") !== challenge.id) {
        while (answerSelect.firstChild) {
          answerSelect.removeChild(answerSelect.firstChild);
        }
        addOption(answerSelect, "", "اختر إجابتك");
        for (var optionIndex = 0; optionIndex < challenge.options.length; optionIndex += 1) {
          addOption(answerSelect, String(optionIndex), challenge.options[optionIndex]);
        }
        answerSelect.setAttribute("data-challenge-id", challenge.id);
        answerSelect.value = "";
      }
      setTextById("challengeTitle", challenge.title);
      setTextById("challengeFamily", challenge.family);
      setTextById("challengeMode", challenge.mode_label || "تحدّي معلومات");
      setTextById(
        "challengeModeHelp",
        challenge.mode_description || "أجب عن السؤال. ستظهر نتيجة التحدي للجميع بعد انتهاء الإجابات."
      );
      setTextById("challengePrompt", challenge.prompt);
      var isDuel = challenge.mode === "duel";
      show(byId("challengeOpponent"), isDuel);
      setTextById(
        "challengeOpponent",
        isDuel
          ? "خصمك في هذه المواجهة: " + (challenge.duel_opponent || "اللاعب المقابل")
          : ""
      );
    }

    if (active) {
      var submitted = !!state.private.challenge_submitted;
      answerSelect.disabled = submitted;
      submitButton.disabled = submitted;
      setNotice(
        "challengeStatus",
        submitted
          ? "وصلت إجابتك السرية. انتظر بقية اللاعبين؛ لن تظهر إجابتك لهم الآن."
          : "أجب قبل انتهاء الوقت. تم تسجيل " + state.challenge_answers_submitted +
            " من " + state.challenge_answer_total + " إجابات.",
        submitted ? "good" : ""
      );
    } else {
      answerSelect.disabled = true;
      submitButton.disabled = true;
    }

    if (result) {
      var revealTitle = result.mode === "duel"
        ? "نتيجة المواجهة — الإجابة الصحيحة: " + result.correct_answer
        : (result.mode === "prediction"
          ? "نتيجة التوقع — المجموع الصحيح: " + result.correct_answer
          : (result.mode === "bluff"
            ? "انكشفت الكذبة — الاختيار الصحيح: " + result.correct_answer
            : "الإجابة الصحيحة: " + result.correct_answer));
      setTextById("challengeCorrectAnswer", revealTitle);
      setTextById("challengeExplanation", result.explanation || "");
      var holder = byId("challengeResults");
      while (holder.firstChild) {
        holder.removeChild(holder.firstChild);
      }
      var duelHolder = byId("challengeDuelResults");
      while (duelHolder.firstChild) {
        duelHolder.removeChild(duelHolder.firstChild);
      }
      var duels = result.duel_results || [];
      show(duelHolder, duels.length > 0);
      for (var duelIndex = 0; duelIndex < duels.length; duelIndex += 1) {
        var duel = duels[duelIndex];
        var duelRow = document.createElement("div");
        duelRow.className = "challenge-duel-row";
        var duelDescription = "";
        if (duel.outcome === "first_won" || duel.outcome === "second_won") {
          duelDescription = duel.winner_name + " فاز بالمواجهة ضد " +
            duel.opponent_name + " وربح " + duel.reward + " عملات.";
        } else if (duel.outcome === "both_correct") {
          duelDescription = "تعادل صحيح! كلا اللاعبين ربح عملتين.";
        } else {
          duelDescription = "لم يقدم أي لاعب إجابة صحيحة؛ لا توجد مكافأة في هذه المواجهة.";
        }
        setText(duelRow, duelDescription);
        duelHolder.appendChild(duelRow);
      }

      var answers = result.answers || [];
      for (var answerIndex = 0; answerIndex < answers.length; answerIndex += 1) {
        var answer = answers[answerIndex];
        var row = document.createElement("div");
        row.className = "challenge-result-row" + (answer.correct ? " success" : "");
        var description = answer.player_name + ": ";
        if (!answer.answered) {
          description += "لم يجب قبل انتهاء الوقت.";
        } else if (answer.correct) {
          description += "إجابة صحيحة — +" + answer.reward + " عملتين.";
        } else {
          description += "إجابة غير صحيحة (" + answer.answer_text + "). لا يوجد خصم.";
        }
        setText(row, description);
        holder.appendChild(row);
      }
    }
  }

  function syncEventFields() {
    if (!match || !match.round_event) {
      return;
    }
    var eventId = match.round_event.id;
    var choice = byId("eventChoice").value;
    var needsTarget = (
      (eventId === "bomb" && choice === "pass") ||
      (eventId === "court" && choice === "vote")
    );
    var needsAmount = eventId === "secret_auction";
    show(byId("eventTargetWrap"), needsTarget);
    show(byId("eventAmountWrap"), needsAmount);
  }

  function renderEventPanel(state) {
    var active = state.phase === "event";
    var event = state.round_event || {};
    var panel = byId("eventPanel");
    var summary = byId("eventResultPanel");
    show(panel, active);
    show(summary, !!state.event_result && !active);

    var eventKey = state.match_id + ":" + state.round + ":" + event.id;
    var eventChanged = (
      event.id && byId("eventChoice").getAttribute("data-event-key") !== eventKey
    );
    if (eventChanged) {
      var choiceSelect = byId("eventChoice");
      while (choiceSelect.firstChild) {
        choiceSelect.removeChild(choiceSelect.firstChild);
      }
      if (event.id === "black_box") {
        addOption(choiceSelect, "", "اختر صندوقًا");
        addOption(choiceSelect, "skip", "أتجاوز اختيار الصندوق");
        addOption(choiceSelect, "0", "الصندوق رقم 1");
        addOption(choiceSelect, "1", "الصندوق رقم 2");
        addOption(choiceSelect, "2", "الصندوق رقم 3");
      } else if (event.id === "bomb") {
        addOption(choiceSelect, "keep", "احتفظ بالقنبلة");
        addOption(choiceSelect, "pass", "مرّر القنبلة");
      } else if (event.id === "secret_auction") {
        addOption(choiceSelect, "bid", "أرسل عرضك السري");
      } else if (event.id === "court") {
        addOption(choiceSelect, "vote", "صوّت على لاعب");
        addOption(choiceSelect, "abstain", "امتنع عن التصويت");
      }
      choiceSelect.setAttribute("data-event-key", eventKey);
      choiceSelect.value = "";
      byId("eventAmount").value = "0";
      byId("eventTarget").value = "";
    }

    if (active) {
      setTextById("eventTitle", event.title || "حدث الجولة");
      setTextById("eventDescription", event.description || "");
      var rule = event.effect || "";
      if (event.id === "bomb" && event.bomb_starter_name) {
        rule += " حامل القنبلة الأول: " + event.bomb_starter_name + ".";
      }
      if (event.id === "temporary_king" && event.king_name) {
        rule += " الملك الحالي: " + event.king_name + ".";
      }
      setTextById(
        "eventRule",
        rule + " لديك 20 ثانية. قرارات الجميع سرية حتى ينتهي الحدث."
      );
      fillTargets(byId("eventTarget"), state.players || [], null, true);

      var submitted = !!state.private.event_submitted;
      var myCoins = 0;
      for (var coinIndex = 0; coinIndex < state.players.length; coinIndex += 1) {
        if (player && state.players[coinIndex].id === player.id) {
          myCoins = state.players[coinIndex].coins;
          break;
        }
      }
      var amountOptions = byId("eventAmount").options;
      for (var amountIndex = 0; amountIndex < amountOptions.length; amountIndex += 1) {
        amountOptions[amountIndex].disabled =
          parseInt(amountOptions[amountIndex].value, 10) > myCoins;
      }
      var selectedAmount = byId("eventAmount").options[byId("eventAmount").selectedIndex];
      if (selectedAmount && selectedAmount.disabled) {
        byId("eventAmount").value = String(Math.min(3, myCoins));
      }
      syncEventFields();
      byId("eventChoice").disabled = submitted;
      byId("eventTarget").disabled = submitted;
      byId("eventAmount").disabled = submitted;
      byId("eventSubmit").disabled = submitted;
      setNotice(
        "eventStatus",
        submitted
          ? "وصل قرارك السري. انتظر بقية اللاعبين؛ لن يظهر اختيارك لهم الآن."
          : "تم تسجيل " + state.event_submitted_count + " من " +
            state.event_submit_total + " قرارات.",
        submitted ? "good" : ""
      );
    } else {
      byId("eventChoice").disabled = true;
      byId("eventTarget").disabled = true;
      byId("eventAmount").disabled = true;
      byId("eventSubmit").disabled = true;
    }

    var outcome = state.event_result;
    if (outcome) {
      setTextById("eventResultTitle", event.title || "نتيجة الحدث");
      setTextById("eventResultDescription", outcome.description || "انتهى الحدث وتم تطبيق أثره.");
      var rows = byId("eventResultRows");
      while (rows.firstChild) {
        rows.removeChild(rows.firstChild);
      }

      if (outcome.event_id === "black_box" || outcome.event_id === "secret_auction") {
        var entries = outcome.entries || [];
        for (var entryIndex = 0; entryIndex < entries.length; entryIndex += 1) {
          var entry = entries[entryIndex];
          var row = document.createElement("div");
          row.className = "challenge-result-row";
          var line = entry.player_name + ": ";
          if (outcome.event_id === "black_box") {
            var boxLabels = {
              bonus: "مكافأة +2 عملتين",
              shield: "حماية مجانية لهذه الجولة",
              trap: entry.delta < 0 ? "فخ — خسر عملة" : "فخ — لا يوجد رصيد لخصمه",
              "لم يختر صندوقًا": "لم يختر صندوقًا قبل انتهاء الوقت"
            };
            line += entry.box ? "الصندوق " + entry.box + " — " : "";
            line += boxLabels[entry.outcome] || entry.outcome;
          } else {
            line += "عرض " + entry.bid + " عملات.";
          }
          setText(row, line);
          rows.appendChild(row);
        }
      } else if (outcome.event_id === "bomb") {
        var pathRow = document.createElement("div");
        pathRow.className = "challenge-result-row";
        setText(pathRow, "مسار القنبلة: " + (outcome.path_names || []).join(" ← "));
        rows.appendChild(pathRow);
      } else if (outcome.event_id === "court") {
        var voteCounts = outcome.vote_counts || [];
        for (var voteIndex = 0; voteIndex < voteCounts.length; voteIndex += 1) {
          var voteRow = document.createElement("div");
          voteRow.className = "challenge-result-row";
          setText(voteRow, voteCounts[voteIndex].player_name + ": " +
            voteCounts[voteIndex].votes + " أصوات");
          rows.appendChild(voteRow);
        }
        var voteEntries = outcome.entries || [];
        for (var ballotIndex = 0; ballotIndex < voteEntries.length; ballotIndex += 1) {
          var ballotRow = document.createElement("div");
          ballotRow.className = "challenge-result-row";
          setText(ballotRow, voteEntries[ballotIndex].player_name +
            " صوّت على: " + voteEntries[ballotIndex].vote_name);
          rows.appendChild(ballotRow);
        }
      } else if (outcome.event_id === "temporary_king") {
        var kingRow = document.createElement("div");
        kingRow.className = "challenge-result-row success";
        setText(kingRow, outcome.king_name + " حصل على عملة التاج والحماية المجانية.");
        rows.appendChild(kingRow);
      }
      if (outcome.shield_names && outcome.shield_names.length) {
        var shieldRow = document.createElement("div");
        shieldRow.className = "challenge-result-row success";
        setText(shieldRow, "حماية مجانية: " + outcome.shield_names.join("، "));
        rows.appendChild(shieldRow);
      }
    }
  }

  function submitEvent() {
    if (!room || mutationBusy || !match || match.phase !== "event" ||
        match.private.event_submitted) {
      return;
    }
    var eventId = match.round_event.id;
    var choice = byId("eventChoice").value;
    if (!choice) {
      setNotice("eventStatus", "اختر قرارك أولًا.", "bad");
      return;
    }
    var body = {
      request_id: makeRequestId(),
      choice_type: choice,
      amount: 0
    };
    if (eventId === "black_box") {
      if (choice === "skip") {
        body.choice_type = "skip";
      } else {
        body.choice_type = "box";
        body.choice_value = parseInt(choice, 10);
      }
    } else if (eventId === "bomb" && choice === "pass") {
      body.target_player_id = byId("eventTarget").value;
      if (!body.target_player_id) {
        setNotice("eventStatus", "اختر اللاعب الذي ستمرر إليه القنبلة.", "bad");
        return;
      }
    } else if (eventId === "secret_auction") {
      body.amount = parseInt(byId("eventAmount").value, 10);
    } else if (eventId === "court" && choice === "vote") {
      body.target_player_id = byId("eventTarget").value;
      if (!body.target_player_id) {
        setNotice("eventStatus", "اختر لاعبًا آخر للتصويت عليه.", "bad");
        return;
      }
    }

    mutationBusy = true;
    byId("eventSubmit").disabled = true;
    setNotice("eventStatus", "جارٍ حفظ قرارك السري...", "");
    request("POST", "/api/rooms/" + encodeURIComponent(room.code) + "/match/event", body,
      function (payload, status) {
        mutationBusy = false;
        if (status === 200 && payload.ok) {
          renderMatch(payload);
        } else {
          byId("eventSubmit").disabled = false;
          setNotice("eventStatus", payload.error || "تعذر حفظ قرار الحدث.", "bad");
        }
        scheduleMatchPoll();
      }
    );
  }

  function renderRoundFlow(state) {
    var phase = state.phase;
    var eventId = state.round_event ? state.round_event.id : "opening";
    var hasInteractiveEvent = (
      eventId === "black_box" || eventId === "bomb" ||
      eventId === "secret_auction" || eventId === "court"
    );
    var currentStep = phase === "challenge" ? 0 :
      (phase === "event" ? 1 :
      (phase === "actions" ? 2 :
      (phase === "revenge" ? 4 :
      (phase === "result" ? 5 : 6))));
    var ids = [
      "flowChallenge", "flowEvent", "flowAction", "flowReveal", "flowRevenge", "flowResult"
    ];
    var hasRevenge = !!(state.result && state.result.revenge_eligible &&
      Object.keys(state.result.revenge_eligible).length);
    for (var i = 0; i < ids.length; i += 1) {
      var item = byId(ids[i]);
      item.className = "round-flow-step";
      if (i === 1) {
        if (phase === "challenge") {
          // The optional event step has not started yet.
        } else if (phase === "event") {
          item.className += " is-current";
        } else if (eventId === "temporary_king" || hasInteractiveEvent) {
          item.className += " is-complete";
        } else {
          item.className += " is-skipped";
        }
      } else if (i === 4 &&
          (phase === "result" || phase === "finished") &&
          !hasRevenge) {
        item.className += " is-skipped";
      } else if (phase === "finished" || i < currentStep) {
        item.className += " is-complete";
      } else if (i === currentStep) {
        item.className += " is-current";
      } else if (i === 4 && phase === "result") {
        item.className += " is-skipped";
      }
      if (i === currentStep) {
        item.setAttribute("aria-current", "step");
      } else {
        item.removeAttribute("aria-current");
      }
    }

    var status = "تبدأ الجولة بسؤال، ثم اختيار سري، ثم كشف النتائج.";
    if (phase === "challenge") {
      status = "أنت الآن في الخطوة 1: " +
        ((state.challenge && state.challenge.mode_description) ||
          "أجب خلال 25 ثانية. الصحيح يمنحك عملتين.");
    } else if (phase === "event") {
      status = "أنت الآن في الخطوة 2: اتخذ قرار حدث الفوضى خلال 20 ثانية. اختيارات الجميع سرية.";
    } else if (phase === "actions") {
      status = hasInteractiveEvent
        ? "أنت الآن في الخطوة 3: اختر حركة واحدة خلال 60 ثانية. تم كشف نتيجة الحدث."
        : "أنت الآن في الخطوة 3: اختر حركة واحدة خلال 60 ثانية. لا يوجد قرار حدث إضافي هذه الجولة.";
    } else if (phase === "revenge") {
      status = "أنت الآن في الخطوة 5: من خسر عملات بالسرقة يقرر الانتقام خلال 15 ثانية.";
    } else if (phase === "result") {
      status = "أنت الآن في الخطوة 6: تم تحديث الأرصدة. تبدأ الجولة التالية بعد 10 ثوانٍ.";
    } else if (phase === "finished") {
      status = "انتهت الجولات الثماني. الترتيب والفائز ظاهران أدناه.";
    }
    if ((phase === "result" || phase === "finished") && !hasRevenge) {
      status += " لا توجد سرقة ناجحة، لذلك تم تجاوز الانتقام.";
    }
    setTextById("roundFlowStatus", status);
  }

  function renderRoundEvent(event) {
    var current = event || {};
    setTextById("roundEventTitle", current.title || "بطاقة فوضى الجولة");
    setTextById("roundEventDescription", current.description || "لا توجد قاعدة إضافية في هذه الجولة.");
    setTextById("roundEventEffect", current.effect || "");
    var eventCard = byId("roundEventCard");
    eventCard.className = "round-event-card" +
      (current.id && current.id !== "opening" ? " round-event-active" : "");
  }

  function toggleRules() {
    var panel = byId("rulesPanel");
    var isHidden = /\bhidden\b/.test(panel.className);
    show(panel, isHidden);
    byId("rulesToggle").setAttribute("aria-expanded", isHidden ? "true" : "false");
    setTextById("rulesToggle", isHidden ? "إخفاء شرح الحركات" : "شرح الحركات — اضغط هنا");
  }

  function submitChallenge() {
    if (!room || mutationBusy || !match || match.phase !== "challenge" ||
        match.private.challenge_submitted) {
      return;
    }
    var value = byId("challengeAnswer").value;
    if (value === "") {
      setNotice("challengeStatus", "اختر إجابة أولًا.", "bad");
      return;
    }
    var answerIndex = parseInt(value, 10);
    if (isNaN(answerIndex)) {
      setNotice("challengeStatus", "الإجابة المختارة غير صالحة.", "bad");
      return;
    }

    mutationBusy = true;
    byId("challengeSubmit").disabled = true;
    byId("challengeAnswer").disabled = true;
    setNotice("challengeStatus", "جارٍ حفظ إجابتك السرية...", "");
    request("POST", "/api/rooms/" + encodeURIComponent(room.code) + "/match/challenge", {
      request_id: makeRequestId(),
      answer_index: answerIndex
    }, function (payload, status) {
      mutationBusy = false;
      if (status === 200 && payload.ok) {
        renderMatch(payload);
      } else {
        byId("challengeSubmit").disabled = false;
        byId("challengeAnswer").disabled = false;
        setNotice("challengeStatus", payload.error || "تعذر حفظ إجابتك.", "bad");
      }
      scheduleMatchPoll();
    });
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

    if (result.event) {
      addEvent("بطاقة الجولة: " + result.event.title + " — " + result.event.description, "warning");
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
        "نجحت السرقة! " + thefts[t].attacker_name + " أخذ " + thefts[t].amount + " من " + thefts[t].target_name +
          (thefts[t].bonus ? " وحصل على مكافأة إضافية قدرها عملة واحدة." : "."),
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
    renderRoundFlow(state);

    renderRoundEvent(state.round_event);
    renderChallenge(state.challenge, state.challenge_result, state);
    renderEventPanel(state);
    show(byId("actionPanel"), state.phase === "actions");
    show(byId("revengePanel"), state.phase === "revenge");
    show(byId("resultPanel"), state.phase === "result" || state.phase === "revenge");
    show(byId("finalPanel"), state.phase === "finished");

    if (state.phase === "challenge") {
      setTextById("phaseTitle", "الخطوة 1 من 6 — " +
        ((state.challenge && state.challenge.mode_label) || "تحدي الجولة"));
      setTextById(
        "phaseDescription",
        (state.challenge && state.challenge.mode_description) ||
          "لديك 25 ثانية للإجابة. لا تبدأ الحركات حتى ينتهي السؤال."
      );
      setNotice(
        "matchNotice",
        "أرسل " + state.challenge_answers_submitted + " من " +
          state.challenge_answer_total + " لاعبين إجاباتهم.",
        ""
      );
    } else if (state.phase === "event") {
      setTextById("phaseTitle", "الخطوة 2 من 6 — " +
        ((state.round_event && state.round_event.title) || "حدث الفوضى"));
      setTextById(
        "phaseDescription",
        (state.round_event && state.round_event.description) ||
          "اتخذ قرارك السري خلال 20 ثانية. لا تظهر قرارات الآخرين قبل الكشف."
      );
      setNotice(
        "matchNotice",
        "أرسل " + state.event_submitted_count + " من " +
          state.event_submit_total + " لاعبين قراراتهم.",
        ""
      );
    } else if (state.phase === "actions") {
      setTextById("phaseTitle", "الخطوة 3 من 6 — الحركة السرية");
      setTextById("phaseDescription", "لديك 60 ثانية لاختيار حركة واحدة: سرقة لاعب، أو حماية نفسك، أو رهان من 1 إلى 3 عملات، أو تمرير. لن يرى أحد اختيارك حتى يكشف الخادم اختيارات الجميع معًا.");
      fillTargets(byId("actionTarget"), state.players || [], null, true);
      var actionLocked = !!state.private.action_submitted;
      var myCoins = 0;
      for (var coinIndex = 0; coinIndex < state.players.length; coinIndex += 1) {
        if (player && state.players[coinIndex].id === player.id) {
          myCoins = state.players[coinIndex].coins;
          break;
        }
      }
      setActionControlsEnabled(!actionLocked);
      var freeGuard = state.round_event && state.round_event.id === "free_guard";
      var temporaryKing = !!state.private.is_temporary_king;
      var guardCost = freeGuard || temporaryKing ? 0 : 1;
      byId("guardAction").disabled = actionLocked || myCoins < guardCost;
      setTextById(
        "guardAction",
        temporaryKing
          ? "درع الملك — احمِ نفسك مجانًا"
          : (freeGuard ? "درع مجاني — احمِ نفسك دون تكلفة" : "احمِ نفسك — التكلفة عملة واحدة")
      );
      setTextById(
        "stealAction",
        temporaryKing
          ? "بصفتك الملك، حاول سرقة حتى 3 عملات"
          : (state.round_event && state.round_event.id === "market_rush"
            ? "حاول سرقة حتى 3 عملات"
            : "حاول سرقة حتى عملتين")
      );
      var wagerOptions = byId("wagerAmount").options;
      for (var wagerIndex = 0; wagerIndex < wagerOptions.length; wagerIndex += 1) {
        wagerOptions[wagerIndex].disabled = parseInt(wagerOptions[wagerIndex].value, 10) > myCoins;
      }
      if (wagerOptions.length && wagerOptions[byId("wagerAmount").selectedIndex] &&
          wagerOptions[byId("wagerAmount").selectedIndex].disabled) {
        byId("wagerAmount").value = myCoins >= 1 ? String(Math.min(3, myCoins)) : "1";
      }
      byId("wagerAction").disabled = actionLocked || myCoins < 1;
      setNotice(
        "actionStatus",
        actionLocked
          ? "تم قفل اختيارك سرًا. انتظر بقية اللاعبين والكشف الجماعي."
          : (freeGuard || temporaryKing)
            ? "اختر حركة واحدة. الحماية مجانية لك في هذه الجولة؛ راجع بطاقة الفوضى قبل القرار."
            : "اختر حركة واحدة. السرقة لا تكلف عملات، والحماية تكلف عملة، والمراهنة بين 1 و3.",
        actionLocked ? "good" : ""
      );
      setNotice(
        "matchNotice",
        "تم تسجيل " + state.actions_submitted + " من " + state.action_total + " اختيارات سرية.",
        ""
      );
    } else if (state.phase === "revenge") {
      setTextById("counterstrikeAction", state.round_event && state.round_event.id === "double_revenge"
        ? "انتقم واسترد حتى عملتين" : "انتقم واسترد عملة واحدة");
      setTextById("phaseTitle", "الخطوة 5 من 6 — نافذة الانتقام");
      setTextById("phaseDescription", "لأن سرقة ناجحة حدثت، يستطيع اللاعب الذي خسر عملات فقط اختيار السارق واسترداد عملة (أو حتى عملتين مع بطاقة الفوضى). لديك 15 ثانية؛ والانتقام لا يفتح انتقامًا جديدًا.");
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
      setTextById("phaseTitle", "الخطوة 6 من 6 — نتيجة الجولة");
      setTextById("phaseDescription", "كشف الخادم كل الاختيارات وحسم أثرها على العملات. راجع من ربح أو خسر؛ بعد 10 ثوانٍ تبدأ الجولة التالية بسؤال جديد.");
      setTextById("resultTitle", "نتائج الجولة " + state.round);
      setNotice("matchNotice", "الجولة التالية تبدأ تلقائيًا بعد انتهاء عدّاد النتائج.", "good");
      renderRoundResult(state.result);
    } else if (state.phase === "finished") {
      setTextById("phaseTitle", "انتهت المباراة — اكتملت المراحل");
      setTextById("phaseDescription", "انتهت الجولات الثماني. تم حسم الأرصدة والترتيب النهائي على الخادم؛ يمكنك مراجعة الفائز والإحصاءات ثم بدء مباراة جديدة.");
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
  byId("rulesToggle").onclick = toggleRules;
  byId("challengeSubmit").onclick = submitChallenge;
  byId("eventSubmit").onclick = submitEvent;
  byId("eventChoice").onchange = syncEventFields;
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
