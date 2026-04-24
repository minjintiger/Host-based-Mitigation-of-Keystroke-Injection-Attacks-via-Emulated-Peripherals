-- name: get_strings()
-- Returns all strings in the form of (id, string, blocked): <Integer, String, Integer Boolean (0 - false, anything else - true)>.
SELECT * 
FROM strings;

-- name: get_blocked_strings()
-- Returns blocked strings in the form of (id, string): <Integer, String> i.e. all those with blocked set to true.
SELECT string_id, string 
FROM strings 
WHERE blocked != 0;

-- name: add_string(string, blocked=false)!
-- Adds string to table, blocked set to false by default.  Overwrites if currently in DB.
INSERT OR REPLACE INTO strings (string, blocked) 
VALUES (:string, :blocked);

-- name: update_string_blocked_by_string(string, blocked)!
-- Updates blocked state of string with value blocked
UPDATE strings 
SET blocked = :blocked 
WHERE string = :string;

-- name: update_string_blocked_by_id(string_id, blocked)!
-- Updates blocked state of string with value blocked
UPDATE strings 
SET blocked = :blocked 
WHERE string_id = :string_id;

-- name: remove_string_by_string(string)!
-- Deletes string from DB
DELETE FROM strings 
WHERE string = :string;

-- name: remove_string_by_id(string_id)!
-- Deletes string from DB
DELETE FROM strings 
WHERE string_id = :string_id;



-- name: get_hotkeys()
-- Returns all hotkeys in the form of (id, hotkey, blocked): <Integer, String, Integer Boolean (0 - false, anything else - true)>.
SELECT * 
FROM hotkeys;

-- name: get_blocked_hotkeys()
-- Returns blocked hotkeys in the form of (id, hotkey): <Integer, String> i.e. all those with blocked set to true.
SELECT hotkey_id, hotkey 
FROM hotkeys 
WHERE blocked != 0;

-- name: add_hotkey(hotkey, blocked=false)!
-- Adds hotkey <String> to table, blocked set to false by default.  Overwrites if currently in DB.
REPLACE INTO hotkeys (hotkey, blocked) 
VALUES (:hotkey, :blocked);

-- name: update_hotkey_blocked_by_hotkey(hotkey, blocked)!
-- Updates blocked state of hotkey <String> with value blocked
UPDATE hotkeys 
SET blocked = :blocked 
WHERE hotkey = :hotkey;

-- name: update_hotkey_blocked_by_id(hotkey_id, blocked)!
-- Updates blocked state of hotkey <String> with value blocked
UPDATE hotkeys 
SET blocked = :blocked 
WHERE hotkey_id = :hotkey_id;

-- name: remove_hotkey_by_hotkey(hotkey)!
-- Deletes hotkey from DB
DELETE FROM hotkeys 
WHERE hotkey = :hotkey;

-- name: remove_hotkey_by_id(hotkey_id)!
-- Deletes hotkey from DB
DELETE FROM hotkeys 
WHERE hotkey_id = :hotkey_id;



-- name: get_hotkey_string_pairs()
-- Returns all strings in the form of (id, hotkey, string, blocked): <Integer, String, StringInteger, Boolean (0 - false, anything else - true)>.
SELECT hotkey_string_combinations.hotkey_string_combination_id, hotkeys.hotkey, strings.string, hotkey_string_combinations.blocked
FROM hotkey_string_combinations
JOIN hotkeys on hotkey_string_combinations.hotkey_id = hotkeys.hotkey_id
JOIN strings on hotkey_string_combinations.string_id = strings.string_id;

-- name: get_blocked_hotkey_string_pairs()
-- Returns all strings in the form of (id, hotkey, string, blocked): <Integer, String, StringInteger, Boolean (0 - false, anything else - true)>.
SELECT hotkey_string_combinations.hotkey_string_combination_id, hotkeys.hotkey, strings.string, hotkey_string_combinations.blocked
FROM hotkey_string_combinations
JOIN hotkeys on hotkey_string_combinations.hotkey_id = hotkeys.hotkey_id
JOIN strings on hotkey_string_combinations.string_id = strings.string_id
WHERE hotkey_string_combinations.blocked != 0;

-- name: add_hotkey_string_pair(hotkey_id, string_id)!
-- Adds hotkey <String>, string <String> pair to table, blocked set to false by default.  Overwrites if currently in DB.
REPLACE INTO hotkey_string_combinations (hotkey_id, string_id) 
VALUES (:hotkey_id, :string_id);

-- name: remove_hotkey_string_pair_by_id(hotkey_string_combination_id)!
-- Removes hotkey <String>, string <String> pair by id
DELETE FROM hotkey_string_combinations
WHERE hotkey_string_combination_id = :hotkey_string_combination_id;



-- name: get_speed_detections()
-- Returns all speed detections in the form of (id, info, detected_at): <Integer, String, String>
SELECT * 
FROM speed_detections;

-- name: add_speed_detection(info, detected_at)!
-- Adds detection to DB where info: String, detected_at: String (consistent date/time format required for stability)
REPLACE INTO speed_detections (info, detected_at)
VALUES (:info, :detected_at);

-- name: remove_speed_detection_by_id(speed_detection_id)!
-- Removes speed detection log entry by given id
DELETE FROM speed_detections
WHERE speed_detection_id = :speed_detection_id;




-- name: get_blacklist_detections()
-- Returns all blacklist detections in the form of (id, hotkey_id, string_id, hotkey_string_combination_id, detected_at): <Integer, Integer, Integer, Integer, String> where only one of the three ids is not null, representing which one was blocked
SELECT * 
FROM blacklist_detections;

-- name: add_blacklist_detection_hotkey(hotkey_id, detected_at)!
-- Adds detection to DB where hotkey_id: Integer, detected_at: String (consistent date/time format required for stability)
REPLACE INTO blacklist_detections (hotkey_id, detected_at)
VALUES (:hotkey_id, :detected_at);

-- name: add_blacklist_detection_string(string_id, detected_at)!
-- Adds detection to DB where string_id: Integer, detected_at: String (consistent date/time format required for stability)
REPLACE INTO blacklist_detections (string_id, detected_at)
VALUES (:string_id, :detected_at);

-- name: add_blacklist_detection_pair(pair_id, detected_at)!
-- Adds detection to DB where pair_id: Integer, detected_at: String (consistent date/time format required for stability)
REPLACE INTO blacklist_detections (hotkey_string_combination_id, detected_at)
VALUES (:pair_id, :detected_at);

-- name: remove_blacklist_detection_by_id(blacklist_detection_id)!
-- Removes blacklist detection log entry by given id
DELETE FROM blacklist_detections
WHERE blacklist_detection_id = :blacklist_detection_id;
