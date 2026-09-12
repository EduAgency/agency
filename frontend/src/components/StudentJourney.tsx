"use client";

/**
 * The student recruitment journey, animated.
 *
 * One shared timeline drives everything: the line draws itself, a bright dash
 * runs just ahead of it, and each stage lights up as the line reaches it
 * rather than on its own independent delay. It loops on an 11s cycle.
 *
 * Three things worth keeping if this is edited:
 *
 *   - `prefers-reduced-motion` collapses it to the finished frame. A
 *     five-stage draw-on is exactly what that preference exists for.
 *   - The keyframe names are prefixed `sj-` and every rule is scoped under
 *     `.student-journey`, so nothing here can leak into the rest of the app.
 *   - The path is real geometry — verticals 260 apart joined by true
 *     semicircles — so it stays crisp at any width. 3720 is just over the
 *     measured path length; changing the path means remeasuring it.
 */

const STYLES = `
.student-journey { width: 100%; }
.student-journey svg { display: block; width: 100%; height: auto; }
.student-journey .sj-stage,
.student-journey .sj-cap,
.student-journey .sj-title { opacity: 0; }

.student-journey .sj-title { animation: sj-title 11s cubic-bezier(.22,1,.36,1) infinite; }
@keyframes sj-title {
  0%      { opacity: 0; transform: translateY(14px); }
  5%, 94% { opacity: 1; transform: translateY(0); }
  100%    { opacity: 0; }
}

.student-journey .sj-track {
  stroke-dasharray: 3720;
  stroke-dashoffset: 3720;
  animation: sj-draw 11s cubic-bezier(.65,.02,.28,1) infinite;
}
@keyframes sj-draw {
  0%       { stroke-dashoffset: 3720; opacity: 1; }
  31%, 94% { stroke-dashoffset: 0; opacity: 1; }
  100%     { stroke-dashoffset: 0; opacity: 0; }
}

.student-journey .sj-comet {
  stroke-dasharray: 8 3712;
  stroke-dashoffset: 3720;
  animation: sj-comet 11s cubic-bezier(.65,.02,.28,1) infinite;
}
@keyframes sj-comet {
  0%   { stroke-dashoffset: 3720; opacity: 0; }
  3%   { opacity: 1; }
  29%  { opacity: 1; }
  31%  { stroke-dashoffset: 0; opacity: 0; }
  100% { stroke-dashoffset: 0; opacity: 0; }
}

.student-journey .sj-cap-start { animation: sj-cap 11s ease-out infinite; }
.student-journey .sj-cap-end   { animation: sj-cap-end 11s ease-out infinite; }
@keyframes sj-cap {
  0%      { opacity: 0; transform: translateX(-10px); }
  4%, 94% { opacity: 1; transform: translateX(0); }
  100%    { opacity: 0; }
}
@keyframes sj-cap-end {
  0%, 31%  { opacity: 0; transform: translateX(-10px); }
  36%, 94% { opacity: 1; transform: translateX(0); }
  100%     { opacity: 0; }
}

.student-journey .sj-stage { transform-box: fill-box; transform-origin: center; }
.student-journey .sj-s1 { animation: sj-stage 11s cubic-bezier(.34,1.4,.44,1) infinite .88s; }
.student-journey .sj-s2 { animation: sj-stage 11s cubic-bezier(.34,1.4,.44,1) infinite 1.54s; }
.student-journey .sj-s3 { animation: sj-stage 11s cubic-bezier(.34,1.4,.44,1) infinite 2.20s; }
.student-journey .sj-s4 { animation: sj-stage 11s cubic-bezier(.34,1.4,.44,1) infinite 2.81s; }
.student-journey .sj-s5 { animation: sj-stage 11s cubic-bezier(.34,1.4,.44,1) infinite 3.41s; }
@keyframes sj-stage {
  0%      { opacity: 0; transform: translateY(18px) scale(.9); }
  6%, 85% { opacity: 1; transform: translateY(0) scale(1); }
  94%     { opacity: 1; }
  100%    { opacity: 0; }
}

.student-journey .sj-num { animation: sj-num 11s cubic-bezier(.22,1,.36,1) infinite; }
.student-journey .sj-s1 .sj-num { animation-delay: .88s; }
.student-journey .sj-s2 .sj-num { animation-delay: 1.54s; }
.student-journey .sj-s3 .sj-num { animation-delay: 2.20s; }
.student-journey .sj-s4 .sj-num { animation-delay: 2.81s; }
.student-journey .sj-s5 .sj-num { animation-delay: 3.41s; }
@keyframes sj-num {
  0%   { filter: blur(7px); opacity: 0; }
  7%   { filter: blur(0); opacity: 1; }
  100% { filter: blur(0); opacity: 1; }
}

.student-journey .sj-icon {
  transform-box: fill-box;
  transform-origin: center;
  animation: sj-float 6.5s ease-in-out infinite;
}
.student-journey .sj-f2 { animation-delay: -1.1s; }
.student-journey .sj-f3 { animation-delay: -2.4s; }
.student-journey .sj-f4 { animation-delay: -3.3s; }
.student-journey .sj-f5 { animation-delay: -4.6s; }
@keyframes sj-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-7px); }
}

.student-journey .sj-band {
  transform-box: fill-box;
  transform-origin: left center;
  animation: sj-band 11s cubic-bezier(.22,1,.36,1) infinite;
}
.student-journey .sj-s1 .sj-band { animation-delay: .88s; }
.student-journey .sj-s2 .sj-band { animation-delay: 1.54s; }
.student-journey .sj-s3 .sj-band { animation-delay: 2.20s; }
.student-journey .sj-s4 .sj-band { animation-delay: 2.81s; }
.student-journey .sj-s5 .sj-band { animation-delay: 3.41s; }
@keyframes sj-band {
  0%       { transform: scaleX(0); }
  8%, 100% { transform: scaleX(1); }
}

@media (prefers-reduced-motion: reduce) {
  .student-journey .sj-stage,
  .student-journey .sj-cap,
  .student-journey .sj-title,
  .student-journey .sj-track,
  .student-journey .sj-icon,
  .student-journey .sj-band,
  .student-journey .sj-num {
    animation: none !important;
    opacity: 1 !important;
    stroke-dashoffset: 0 !important;
    filter: none !important;
    transform: none !important;
  }
  .student-journey .sj-comet { animation: none !important; opacity: 0 !important; }
}
`;

const PATH =
  "M 95 490 H 130 A 55 55 0 0 1 185 545 V 640 A 127.5 127.5 0 0 0 440 640 V 335 " +
  "A 130 130 0 0 1 700 335 V 640 A 130 130 0 0 0 960 640 V 335 A 132.5 132.5 0 0 1 1225 335 " +
  "V 640 A 132.5 132.5 0 0 0 1490 640 V 545 A 55 55 0 0 1 1545 490 H 1580";

export function StudentJourney() {
  return (
    <div className="student-journey">
      {/* Keyframes with per-stage delays do not express usefully as utility
          classes, so the animation ships as one scoped stylesheet. */}
      <style dangerouslySetInnerHTML={{ __html: STYLES }} />

      <svg
        viewBox="0 0 1656 930"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="The student recruitment journey, in five stages: engagement, application, decision, planning, arrival."
      >
        <defs>
          <linearGradient id="sjFlow" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#0f4c9b" />
            <stop offset=".42" stopColor="#175fae" />
            <stop offset=".72" stopColor="#2a8cb8" />
            <stop offset="1" stopColor="#37acb6" />
          </linearGradient>
          <linearGradient id="sjBand" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#ffffff" stopOpacity="0" />
            <stop offset=".2" stopColor="#ffffff" stopOpacity=".85" />
            <stop offset=".8" stopColor="#ffffff" stopOpacity=".85" />
            <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
        </defs>

        <rect width="1656" height="930" fill="#e9f6f4" />

        <text
          className="sj-title"
          x="828"
          y="106"
          textAnchor="middle"
          fontSize="47"
          fontWeight="800"
          fill="#1553a8"
        >
          The Student Recruitment Journey
        </text>

        <path
          className="sj-track"
          d={PATH}
          fill="none"
          stroke="url(#sjFlow)"
          strokeWidth="11"
          strokeLinecap="round"
        />
        <path
          className="sj-comet"
          d={PATH}
          fill="none"
          stroke="#8fe9ec"
          strokeWidth="13"
          strokeLinecap="round"
        />

        <g className="sj-cap sj-cap-start">
          <path
            d="M 62 466 L 88 490 L 62 514"
            fill="none"
            stroke="#0f4c9b"
            strokeWidth="11"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>
        <g className="sj-cap sj-cap-end">
          <path
            d="M 1588 466 L 1614 490 L 1588 514"
            fill="none"
            stroke="#37acb6"
            strokeWidth="11"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>

        {/* 01 Engagement */}
        <g className="sj-stage sj-s1">
          <text className="sj-num" x="310" y="478" textAnchor="middle" fontSize="58" fontWeight="700" fill="#175fae">01</text>
          <rect className="sj-band" x="180" y="518" width="260" height="44" fill="url(#sjBand)" />
          <text x="310" y="548" textAnchor="middle" fontSize="20" fontWeight="700" fill="#1553a8">Engagement</text>
          <g className="sj-icon sj-f1">
            <circle cx="318" cy="672" r="62" fill="#d7ebf7" />
            <rect x="252" y="626" width="104" height="40" rx="5" fill="#fff" stroke="#1f5fa8" strokeWidth="2.5" />
            <circle cx="270" cy="646" r="9" fill="#31c4a4" />
            <rect x="286" y="638" width="56" height="5.5" rx="2.75" fill="#9fc4e4" />
            <rect x="286" y="649" width="40" height="5.5" rx="2.75" fill="#cfe2f2" />
            <rect x="252" y="674" width="104" height="40" rx="5" fill="#fff" stroke="#1f5fa8" strokeWidth="2.5" />
            <circle cx="270" cy="694" r="9" fill="#31c4a4" />
            <rect x="286" y="686" width="56" height="5.5" rx="2.75" fill="#9fc4e4" />
            <rect x="286" y="697" width="40" height="5.5" rx="2.75" fill="#cfe2f2" />
            <circle cx="333" cy="659" r="30" fill="#eaf4fb" fillOpacity=".85" stroke="#1f5fa8" strokeWidth="6" />
            <path d="M 352 682 L 374 706" stroke="#1f5fa8" strokeWidth="11" strokeLinecap="round" />
            <path d="M 356 686 L 378 710" stroke="#f4b93e" strokeWidth="6" strokeLinecap="round" />
          </g>
        </g>

        {/* 02 Application */}
        <g className="sj-stage sj-s2">
          <text className="sj-num" x="575" y="322" textAnchor="middle" fontSize="58" fontWeight="700" fill="#1a66b2">02</text>
          <rect className="sj-band" x="445" y="352" width="260" height="44" fill="url(#sjBand)" />
          <text x="575" y="382" textAnchor="middle" fontSize="20" fontWeight="700" fill="#1553a8">Application</text>
          <g className="sj-icon sj-f2">
            <circle cx="584" cy="510" r="62" fill="#d7ebf7" />
            <rect x="527" y="452" width="98" height="122" rx="8" fill="#2fae9b" />
            <rect x="537" y="464" width="78" height="100" rx="4" fill="#fff" />
            <rect x="561" y="443" width="30" height="18" rx="5" fill="#1f8f7f" />
            <circle cx="576" cy="443" r="6" fill="#1f8f7f" />
            <rect x="548" y="480" width="56" height="7" rx="3.5" fill="#bfe0f2" />
            <rect x="548" y="495" width="40" height="7" rx="3.5" fill="#e2eef7" />
            <rect x="548" y="510" width="50" height="7" rx="3.5" fill="#e2eef7" />
            <rect x="548" y="525" width="34" height="7" rx="3.5" fill="#e2eef7" />
            <path d="M 520 542 L 592 476" stroke="#1b3f6b" strokeWidth="8" strokeLinecap="round" />
            <path d="M 588 480 L 600 468" stroke="#f4b93e" strokeWidth="9" strokeLinecap="round" />
            <path d="M 512 556 q 14 -22 34 -16 q 16 5 24 16 l 8 22 q -34 12 -60 4 z" fill="#c97a4a" />
            <path d="M 512 556 q 14 -22 34 -16 l -6 14 q -16 -2 -28 2 z" fill="#b56a3e" />
          </g>
        </g>

        {/* 03 Decision */}
        <g className="sj-stage sj-s3">
          <text className="sj-num" x="837" y="478" textAnchor="middle" fontSize="58" fontWeight="700" fill="#175fae">03</text>
          <rect className="sj-band" x="707" y="518" width="260" height="44" fill="url(#sjBand)" />
          <text x="837" y="548" textAnchor="middle" fontSize="20" fontWeight="700" fill="#1553a8">Decision</text>
          <g className="sj-icon sj-f3">
            <circle cx="845" cy="672" r="62" fill="#d7ebf7" />
            <rect x="762" y="622" width="72" height="98" rx="7" fill="#1f5fa8" />
            <rect x="770" y="630" width="56" height="82" rx="4" fill="#2a72c0" />
            <circle cx="798" cy="662" r="17" fill="none" stroke="#bfe0f2" strokeWidth="2.5" />
            <path d="M 781 662 h 34 M 798 645 q 9 17 0 34 M 798 645 q -9 17 0 34" stroke="#bfe0f2" strokeWidth="2.5" fill="none" />
            <rect x="784" y="690" width="28" height="5" rx="2.5" fill="#bfe0f2" />
            <path d="M 822 616 h 62 l 22 22 v 84 a 6 6 0 0 1 -6 6 h -78 a 6 6 0 0 1 -6 -6 v -100 a 6 6 0 0 1 6 -6 z" fill="#fff" stroke="#dbe8f2" strokeWidth="2" />
            <path d="M 884 616 v 22 h 22 z" fill="#f4d9c4" />
            <rect x="834" y="640" width="26" height="18" rx="3" fill="#f2b9c4" />
            <text x="872" y="654" textAnchor="middle" fontSize="15" fontWeight="800" fill="#e0607a">VISA</text>
            <rect x="834" y="668" width="60" height="6" rx="3" fill="#dbe8f2" />
            <rect x="834" y="682" width="46" height="6" rx="3" fill="#eaf1f7" />
            <rect x="834" y="696" width="54" height="6" rx="3" fill="#eaf1f7" />
            <circle cx="886" cy="710" r="23" fill="#2fbf9b" />
            <path d="M 875 710 l 7 8 l 14 -16" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        </g>

        {/* 04 Planning */}
        <g className="sj-stage sj-s4">
          <text className="sj-num" x="1100" y="322" textAnchor="middle" fontSize="58" fontWeight="700" fill="#2a8cb8">04</text>
          <rect className="sj-band" x="970" y="352" width="260" height="44" fill="url(#sjBand)" />
          <text x="1100" y="382" textAnchor="middle" fontSize="20" fontWeight="700" fill="#1a6fa8">Planning</text>
          <g className="sj-icon sj-f4">
            <circle cx="1094" cy="510" r="62" fill="#d7ebf7" />
            <rect x="1112" y="492" width="58" height="72" rx="9" fill="#f4c268" />
            <rect x="1112" y="492" width="58" height="72" rx="9" fill="none" stroke="#e0a93f" strokeWidth="2" />
            <path d="M 1141 492 v 72" stroke="#e0a93f" strokeWidth="3" />
            <path d="M 1126 492 v -12 a 15 15 0 0 1 30 0 v 12" fill="none" stroke="#e0a93f" strokeWidth="5" />
            <path d="M 1052 452 v -14 h 30 v 14" fill="none" stroke="#7f8b93" strokeWidth="6" strokeLinecap="round" />
            <rect x="1032" y="452" width="70" height="112" rx="13" fill="#2fae9b" />
            <rect x="1032" y="452" width="70" height="112" rx="13" fill="none" stroke="#1f8f7f" strokeWidth="2.5" />
            <path d="M 1056 452 v 112 M 1078 452 v 112" stroke="#1f8f7f" strokeWidth="3" opacity=".55" />
            <rect x="1040" y="470" width="22" height="16" rx="3" fill="#fff" opacity=".9" />
            <circle cx="1075" cy="518" r="11" fill="#fff" opacity=".9" />
            <circle cx="1075" cy="518" r="5" fill="#2fae9b" />
            <rect x="1038" y="566" width="12" height="9" rx="3" fill="#7f8b93" />
            <rect x="1084" y="566" width="12" height="9" rx="3" fill="#7f8b93" />
          </g>
        </g>

        {/* 05 Arrival */}
        <g className="sj-stage sj-s5">
          <text className="sj-num" x="1365" y="478" textAnchor="middle" fontSize="58" fontWeight="700" fill="#37acb6">05</text>
          <rect className="sj-band" x="1235" y="518" width="260" height="44" fill="url(#sjBand)" />
          <text x="1365" y="548" textAnchor="middle" fontSize="20" fontWeight="700" fill="#2a93a8">Arrival</text>
          <g className="sj-icon sj-f5">
            <circle cx="1360" cy="672" r="62" fill="#d7ebf7" />
            <g transform="rotate(-9 1350 676)">
              <rect x="1300" y="628" width="108" height="72" rx="7" fill="#f4c268" />
              <rect x="1300" y="628" width="108" height="72" rx="7" fill="none" stroke="#e0a93f" strokeWidth="2" />
            </g>
            <g transform="rotate(6 1356 680)">
              <rect x="1306" y="640" width="112" height="76" rx="7" fill="#fff" stroke="#dbe8f2" strokeWidth="2" />
              <rect x="1314" y="650" width="30" height="24" rx="4" fill="#cfe2f2" />
              <circle cx="1329" cy="659" r="6" fill="#7fb0da" />
              <path d="M 1322 671 q 7 -7 14 0 z" fill="#7fb0da" />
              <rect x="1352" y="650" width="56" height="6" rx="3" fill="#dbe8f2" />
              <rect x="1352" y="662" width="40" height="6" rx="3" fill="#eaf1f7" />
              <path d="M 1306 682 h 112" stroke="#dbe8f2" strokeWidth="2" strokeDasharray="5 4" />
              <rect x="1314" y="692" width="34" height="16" rx="3" fill="#f2b9c4" />
              <rect x="1356" y="694" width="52" height="6" rx="3" fill="#eaf1f7" />
            </g>
            <g transform="rotate(-14 1404 660)">
              <rect x="1386" y="640" width="40" height="26" rx="5" fill="#e0607a" />
              <rect x="1398" y="666" width="16" height="20" rx="4" fill="#c94c66" />
              <rect x="1390" y="686" width="32" height="9" rx="4" fill="#e0607a" />
            </g>
          </g>
        </g>
      </svg>
    </div>
  );
}
