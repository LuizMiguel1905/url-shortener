import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const CODE = "loadtest";
const JSON_HEADERS = { headers: { "Content-Type": "application/json" } };

export const options = {
  vus: Number(__ENV.VUS || 50),
  duration: __ENV.DURATION || "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
    checks: ["rate>0.99"],
  },
};

export function setup() {
  const response = http.post(
    `${BASE_URL}/links`,
    JSON.stringify({ url: "https://example.com/loadtest", custom_code: CODE }),
    JSON_HEADERS,
  );
  check(response, { "setup: link exists": (r) => r.status === 201 || r.status === 409 });
}

export default function () {
  if (Math.random() < 0.1) {
    const response = http.post(
      `${BASE_URL}/links`,
      JSON.stringify({ url: "https://example.com/page" }),
      JSON_HEADERS,
    );
    check(response, { "create: 201": (r) => r.status === 201 });
    return;
  }
  const response = http.get(`${BASE_URL}/${CODE}`, { redirects: 0 });
  check(response, { "redirect: 307": (r) => r.status === 307 });
}
