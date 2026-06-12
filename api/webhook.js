export default async function handler(req, res) {
  if (req.method === "GET") return res.status(200).send("OFF90 Webhook OK");
  if (req.method !== "POST") return res.status(405).send("Method Not Allowed");

  const utterance = (req.body?.userRequest?.utterance ?? "").trim();

  if (utterance === "승인") {
    const resp = await fetch(
      `https://api.github.com/repos/${process.env.GITHUB_REPO}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
          "User-Agent": "OFF90-Kakao-Bot",
        },
        body: JSON.stringify({ event_type: "kakao-approve" }),
      }
    );
    const text = resp.status === 204
      ? "✅ 승인 완료!\n\n인스타 발행을 시작합니다.\n약 2~3분 후 @the.off90 에 게시됩니다."
      : "⚠️ 발행 트리거 실패 (" + resp.status + ")";
    return res.status(200).json(kakaoReply(text));
  }

  if (utterance === "거절" || utterance === "취소") {
    return res.status(200).json(kakaoReply("❌ 발행이 취소되었습니다."));
  }

  return res.status(200).json(
    kakaoReply("⚽ OFF90봇\n\n• 승인 — 콘텐츠 발행\n• 거절 — 발행 취소")
  );
}

function kakaoReply(text) {
  return {
    version: "2.0",
    template: { outputs: [{ simpleText: { text } }] },
  };
}
