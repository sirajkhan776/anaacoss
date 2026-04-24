# Anaacoss Android Wrapper

This folder contains a minimal Android WebView app for `https://anaacoss.in`.

## Open In Android Studio

1. Open Android Studio.
2. Choose `Open`.
3. Select the [`android`](./) folder.
4. Let Gradle sync complete.

## Build Debug APK

1. In Android Studio, open the `Build` menu.
2. Click `Build Bundle(s) / APK(s)`.
3. Click `Build APK(s)`.

The generated APK will usually be available at:

- `android/app/build/outputs/apk/debug/app-debug.apk`

## Notes

- The app loads the live production site: `https://anaacoss.in`
- Pull to refresh is enabled.
- Back button navigates back inside the WebView before closing the app.
- JavaScript and DOM storage are enabled because the storefront depends on them.
