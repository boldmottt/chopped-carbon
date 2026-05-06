// Forged Carbon vectorize - Illustrator menu script (macOS)
//
// Pairs with the Python tool installed by install.sh at ~/.forge_carbon/.
// Illustrator's JSX cannot run shell commands directly (no `system` object),
// so we delegate to a small AppleScript runner.app that install.sh builds.
//
// Pipeline: JSX writes ~/.forge_carbon/request.sh, launches runner.app,
// polls for output SVG, then opens it in Illustrator.

#target illustrator

(function () {
    var INSTALL = "~/.forge_carbon";

    function P(p) { return new File(p); }

    var runner = P(INSTALL + "/runner.app");
    if (!runner.exists) {
        alert(
            "runner.app 가 없습니다.\n"
            + "터미널에서 install.sh 를 다시 실행하세요:\n\n"
            + "  cd <repo>\n  ./install.sh"
        );
        return;
    }

    // ---------- 1. pick image ----------
    var inputFile = File.openDialog(
        "포지드 카본 스캔 이미지 선택",
        "Image:*.jpg;*.jpeg;*.png;*.tif;*.tiff"
    );
    if (!inputFile) return;

    // ---------- 2. parameter dialog ----------
    var dlg = new Window("dialog", "Forged Carbon Vectorize");
    dlg.orientation = "column";
    dlg.alignChildren = "fill";
    dlg.margins = 16;
    dlg.spacing = 10;

    function row(parent, label, def) {
        var g = parent.add("group");
        g.alignment = "fill";
        var lbl = g.add("statictext", undefined, label);
        lbl.preferredSize.width = 180;
        var et = g.add("edittext", undefined, String(def));
        et.preferredSize.width = 80;
        return et;
    }

    var p1 = dlg.add("panel", undefined, "Resolution & density");
    p1.alignChildren = "fill";
    p1.margins = 12;
    var maxDim = row(p1, "최대 변 길이 (px)", "3000");
    var spacing = row(p1, "섬유 간격 (px)", "5");
    var stroke = row(p1, "라인 두께 (px)", "0.5");

    var p2 = dlg.add("panel", undefined, "Tone");
    p2.alignChildren = "fill";
    p2.margins = 12;
    var fiberLo = row(p2, "섬유 최소 명도 (0-255)", "150");
    var fiberHi = row(p2, "섬유 최대 명도 (0-255)", "250");
    var bg = row(p2, "배경 명도 (0-255)", "6");

    var p3 = dlg.add("panel", undefined, "Options");
    p3.alignChildren = "left";
    p3.margins = 12;
    var chipFills = p3.add("checkbox", undefined, "칩 채움 그리기");
    chipFills.value = true;
    var clahe = p3.add("checkbox", undefined, "CLAHE 적용 (대비 강화)");
    clahe.value = true;
    var openResult = p3.add("checkbox", undefined, "완료 후 새 도큐먼트로 열기");
    openResult.value = true;

    var btns = dlg.add("group");
    btns.alignment = "right";
    btns.add("button", undefined, "취소", { name: "cancel" });
    btns.add("button", undefined, "생성", { name: "ok" });

    if (dlg.show() != 1) return;

    // ---------- 3. paths ----------
    var outDir = inputFile.parent.fsName;
    var baseName = inputFile.name.replace(/\.[^.]+$/, "");
    var outPath = outDir + "/" + baseName + "_forged.svg";
    var outFile = new File(outPath);
    var doneFile = new File(outPath + ".done");
    var failFile = new File(outPath + ".fail");
    var logPath = "/tmp/forged_carbon.log";

    if (outFile.exists) outFile.remove();
    if (doneFile.exists) doneFile.remove();
    if (failFile.exists) failFile.remove();

    // ---------- 4. compose request.sh ----------
    function shq(s) {
        return "'" + String(s).replace(/'/g, "'\\''") + "'";
    }

    var py = INSTALL + "/.venv/bin/python";
    var script = INSTALL + "/forge_vectorize.py";

    var pyParts = [
        shq(py), shq(script),
        shq(inputFile.fsName),
        "-o", shq(outPath),
        "--max-dim", maxDim.text,
        "--spacing", spacing.text,
        "--stroke-width", stroke.text,
        "--fiber-lo", fiberLo.text,
        "--fiber-hi", fiberHi.text,
        "--bg", bg.text
    ];
    if (chipFills.value) pyParts.push("--draw-chip-fills");
    if (clahe.value) pyParts.push("--clahe");

    var lines = [
        "#!/bin/bash",
        "set +e",
        pyParts.join(" ") + " > " + shq(logPath) + " 2>&1",
        "if [ $? -eq 0 ]; then touch " + shq(outPath + ".done") + ";"
        + " else touch " + shq(outPath + ".fail") + "; fi"
    ];

    var requestPath = INSTALL.replace(/^~/, Folder.userData.parent.fsName)
        + "/request.sh";
    // Folder.userData = ~/Library/Application Support; .parent = ~/Library; not what we want.
    // Easier: use Folder.userHome
    requestPath = Folder("~").fsName + "/.forge_carbon/request.sh";
    var requestFile = new File(requestPath);
    requestFile.encoding = "UTF-8";
    requestFile.open("w");
    requestFile.write(lines.join("\n") + "\n");
    requestFile.close();

    // ---------- 5. launch runner.app and poll ----------
    var t0 = (new Date()).getTime();
    runner.execute();

    var timeoutMs = 15 * 60 * 1000; // 15 min
    var deadline = t0 + timeoutMs;
    while ((new Date()).getTime() < deadline) {
        if (doneFile.exists || failFile.exists) break;
        $.sleep(500);
    }
    var elapsed = (((new Date()).getTime() - t0) / 1000).toFixed(1);

    // ---------- 6. result ----------
    if (doneFile.exists) {
        doneFile.remove();
        if (openResult.value && outFile.exists) {
            try { app.open(outFile); }
            catch (e) { alert("자동 열기 실패: " + e); }
        }
        alert("완료 (" + elapsed + "초)\n\n" + outPath);
    } else {
        if (failFile.exists) failFile.remove();
        var log = "";
        var lf = new File(logPath);
        if (lf.exists) {
            lf.encoding = "UTF-8";
            lf.open("r");
            log = lf.read();
            lf.close();
        }
        var tail = log.length > 1500 ? log.substring(log.length - 1500) : log;
        alert(
            "실패 또는 타임아웃 (" + elapsed + "초)\n\n"
            + "로그 (말미):\n" + (tail || "(로그 비어 있음)")
        );
    }
})();
