/** @type {import('jest').Config} */
module.exports = {
    testEnvironment: "jsdom",
    roots: ["<rootDir>/script_consent/static/script_consent/js"],
    testMatch: ["**/?(*.)+(spec|test).js"],
    collectCoverageFrom: ["<rootDir>/script_consent/static/script_consent/js/*.js"],
    coverageDirectory: "<rootDir>/coverage-js",
};
