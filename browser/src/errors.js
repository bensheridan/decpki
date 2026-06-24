export class UnsupportedBrowserError extends Error {
  constructor(message = 'Browser lacks required cryptographic APIs (crypto.subtle or indexedDB)') {
    super(message);
    this.name = 'UnsupportedBrowserError';
  }
}

export class BundleValidationError extends Error {
  constructor(reason, message) {
    super(message || `Bundle validation failed: ${reason}`);
    this.name = 'BundleValidationError';
    this.reason = reason;
  }
}
