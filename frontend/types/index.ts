export type PhotoStatus = "UPLOADING" | "PROCESSING" | "READY" | "FAILED";
export type EventStatus = "LIVE" | "ARCHIVED";

export interface User {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface EventStats {
  photos: number;
  processed: number;
  processing: number;
  failed: number;
  faces: number;
  guests: number;
  matches: number;
}

export interface Event {
  id: string;
  name: string;
  event_code: string;
  event_date: string | null;
  location: string | null;
  description: string | null;
  status: EventStatus;
  public_access: boolean;
  retention_days: number | null;
  created_at: string;
  updated_at: string;
  public_url: string;
  stats?: EventStats;
}

export interface Photo {
  id: string;
  filename: string;
  status: PhotoStatus;
  file_size: number;
  width: number | null;
  height: number | null;
  face_count: number;
  error: string | null;
  created_at: string;
  thumbnail_url: string;
  original_url: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface DashboardStats {
  total_events: number;
  active_events: number;
  total_photos: number;
  photos_delivered: number;
  total_guests: number;
}

export interface Dashboard {
  stats: DashboardStats;
  recent_events: Event[];
}

export interface PublicEvent {
  name: string;
  event_code: string;
  event_date: string | null;
  location: string | null;
  description: string | null;
  photo_count: number;
  is_live: boolean;
}

export interface Match {
  photo: Photo;
  similarity: number;
}

export interface SearchResult {
  search_id: string;
  event_code: string;
  match_count: number;
  threshold: number;
  matches: Match[];
  created_at: string;
}

export type SelfieErrorCode =
  | "NO_FACE"
  | "MULTIPLE_FACES"
  | "INVALID_IMAGE"
  | "ENGINE_UNAVAILABLE";

export interface UploadItemResult {
  filename: string;
  status: "uploaded" | "duplicate" | "rejected";
  photo: Photo | null;
  error: string | null;
}

export interface UploadResponse {
  uploaded: number;
  duplicates: number;
  rejected: number;
  results: UploadItemResult[];
}
