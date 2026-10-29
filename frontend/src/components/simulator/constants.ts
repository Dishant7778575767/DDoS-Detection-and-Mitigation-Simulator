import type { ScenarioType } from "@/types";

export interface ScenarioInfo {
  title: string;
  subtitle: string;
  desc: string;
}

export const SCENARIO_DESCRIPTIONS: Record<ScenarioType, ScenarioInfo> = {
  syn_flood: {
    title: "Connection Overload Attack (SYN Flood)",
    subtitle: "Spamming fake phone calls until the line goes busy",
    desc: "Attackers send millions of half-open connection requests. The server waits endlessly for them to finish, running out of memory so real visitors cannot connect.",
  },
  udp_flood: {
    title: "Bandwidth Choke Attack (UDP Flood)",
    subtitle: "Clogging the internet pipe with giant junk data",
    desc: "Blasts huge volumes of random data packets to exhaust network bandwidth. Real user traffic gets blocked by pure congestion.",
  },
  http_flood: {
    title: "Website Overload Attack (HTTP Flood)",
    subtitle: "Botnets hitting Refresh button millions of times",
    desc: "A swarm of fake bots endlessly requests heavy web pages, draining server CPU and crashing the web application.",
  },
  low_and_slow: {
    title: "Sneaky Stealth Attack (Slowloris)",
    subtitle: "Creeping slowly under the radar without alarm bells",
    desc: "Sends tiny fragments of data extremely slowly. Traditional volume alarms don't trigger, but server connections get locked up one by one.",
  },
  mixed: {
    title: "Combined Multi-Vector Attack",
    subtitle: "Simultaneous attack on bandwidth, connections, and website",
    desc: "Combines connection overload, bandwidth flooding, and web spam simultaneously to test full AI defense resilience.",
  },
  flash_crowd: {
    title: "Viral Traffic Spike (Safe Real Visitors - NOT an Attack!)",
    subtitle: "Sudden wave of genuine happy users (e.g. viral news / sale)",
    desc: "A massive surge of legitimate real customers. SENTRIX proves its AI intelligence by NEVER blocking real people by accident (zero false alarms).",
  },
};

