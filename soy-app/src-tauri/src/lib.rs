mod claude;
mod commands;
mod db;
pub mod google;
mod state;
pub mod tools;

use state::AppState;
use tauri::image::Image;
use tauri::menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Emitter, Manager, WebviewUrl, WebviewWindowBuilder, WindowEvent};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState::new())
        .invoke_handler(tauri::generate_handler![
            commands::send_message,
            commands::get_api_key_status,
            commands::set_api_key,
            commands::get_panel_data,
            commands::connect_google,
            commands::disconnect_google,
            commands::get_google_status,
            commands::get_onboarding_state,
            commands::create_conversation,
            commands::get_recent_conversation,
            commands::save_message,
            commands::sync_gmail,
            commands::sync_calendar,
        ])
        .setup(|app| {
            // Auto-sync: refresh Gmail + Calendar data on startup (after 10s)
            // and then every 15 minutes.
            let sync_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                // Short delay on startup so the app is fully loaded before first sync.
                tokio::time::sleep(std::time::Duration::from_secs(10)).await;

                loop {
                    let state = sync_handle.state::<AppState>();
                    let db = state.db.clone();
                    let token = match state.google_auth.get_valid_token(&db).await {
                        Ok(Some(t)) => t,
                        _ => {
                            // Not connected or token error — wait and retry.
                            tokio::time::sleep(std::time::Duration::from_secs(900)).await;
                            continue;
                        }
                    };

                    if let Err(e) = google::gmail::sync_gmail(&db, &token, 50).await {
                        eprintln!("Auto-sync gmail error: {}", e);
                    }
                    if let Err(e) = google::calendar::sync_calendar(&db, &token).await {
                        eprintln!("Auto-sync calendar error: {}", e);
                    }

                    // Wait 15 minutes before next sync cycle.
                    tokio::time::sleep(std::time::Duration::from_secs(900)).await;
                }
            });

            // ── macOS-native menus (Quit, Copy/Paste, etc.) ─────────────
            let prefs_item = MenuItemBuilder::new("Settings...")
                .accelerator("CmdOrCtrl+,")
                .id("preferences")
                .build(app)?;

            let app_menu = SubmenuBuilder::new(app, "Software of You")
                .item(&PredefinedMenuItem::about(app, None, None)?)
                .separator()
                .item(&prefs_item)
                .separator()
                .item(&PredefinedMenuItem::hide(app, None)?)
                .item(&PredefinedMenuItem::hide_others(app, None)?)
                .item(&PredefinedMenuItem::show_all(app, None)?)
                .separator()
                .item(&PredefinedMenuItem::quit(app, None)?)
                .build()?;

            let edit_menu = SubmenuBuilder::new(app, "Edit")
                .item(&PredefinedMenuItem::undo(app, None)?)
                .item(&PredefinedMenuItem::redo(app, None)?)
                .separator()
                .item(&PredefinedMenuItem::cut(app, None)?)
                .item(&PredefinedMenuItem::copy(app, None)?)
                .item(&PredefinedMenuItem::paste(app, None)?)
                .item(&PredefinedMenuItem::select_all(app, None)?)
                .build()?;

            let window_menu = SubmenuBuilder::new(app, "Window")
                .item(&PredefinedMenuItem::minimize(app, None)?)
                .item(&PredefinedMenuItem::close_window(app, None)?)
                .build()?;

            let menu = MenuBuilder::new(app)
                .item(&app_menu)
                .item(&edit_menu)
                .item(&window_menu)
                .build()?;
            app.set_menu(menu)?;

            // Handle the Preferences menu click
            let prefs_handle = app.handle().clone();
            app.on_menu_event(move |_app, event| {
                if event.id().0 == "preferences" {
                    // Emit an event to the frontend to open settings panel
                    let _ = prefs_handle.emit(
                        "open-settings",
                        serde_json::json!({ "type": "settings", "title": "Settings" }),
                    );
                }
            });

            // ── Menu-bar tray icon ──────────────────────────────────────
            let icon = Image::from_path("icons/32x32.png")
                .unwrap_or_else(|_| Image::from_bytes(include_bytes!("../icons/32x32.png")).expect("bundled tray icon"));

            let _tray = TrayIconBuilder::new()
                .icon(icon)
                .icon_as_template(true)
                .tooltip("Software of You")
                .show_menu_on_left_click(false)
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(win) = app.get_webview_window("menubar") {
                            if win.is_visible().unwrap_or(false) {
                                let _ = win.hide();
                            } else {
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        } else {
                            // Create the menubar window on first click.
                            let _ = WebviewWindowBuilder::new(
                                app,
                                "menubar",
                                WebviewUrl::App("index.html".into()),
                            )
                            .title("")
                            .inner_size(320.0, 480.0)
                            .resizable(false)
                            .decorations(false)
                            .always_on_top(true)
                            .skip_taskbar(true)
                            .shadow(true)
                            .visible(true)
                            .build();
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        // Hide the menubar popover when it loses focus.
        .on_window_event(|window, event| {
            if window.label() == "menubar" {
                if let WindowEvent::Focused(false) = event {
                    let _ = window.hide();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
