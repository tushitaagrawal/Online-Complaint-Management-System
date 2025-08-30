-- Create database
CREATE DATABASE IF NOT EXISTS complaints_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE complaints_db;

-- Users table
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(150) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('user','admin') NOT NULL DEFAULT 'user',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Complaints table
CREATE TABLE IF NOT EXISTS complaints (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  title VARCHAR(200) NOT NULL,
  category VARCHAR(100) NOT NULL,
  description TEXT NOT NULL,
  status ENUM('Submitted','In Progress','Resolved','Closed') NOT NULL DEFAULT 'Submitted',
  priority ENUM('Low','Medium','High') NOT NULL DEFAULT 'Medium',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Complaint history table(audit trail)
CREATE TABLE IF NOT EXISTS complaint_history (
  id INT AUTO_INCREMENT PRIMARY KEY,
  complaint_id INT NOT NULL,
  action_by INT ,
  old_status VARCHAR(50),
  new_status VARCHAR(50),
  note TEXT,
  action_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
  FOREIGN KEY(action_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Feedback table
CREATE TABLE IF NOT EXISTS feedback (
  id INT AUTO_INCREMENT PRIMARY KEY,
  complaint_id INT NOT NULL,
  user_id INT NOT NULL,
  rating INT CHECK (rating BETWEEN 1 AND 5),
  comments TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create a default admin (change password later from UI)
INSERT IGNORE INTO users(name,email,password_hash,role)
VALUES('Admin','admin@example.com','$2b$12$Qd2xF1UjM2q5u9a3p3b5Eui5K3v7qJ3nYkQK9m9uY1k8Q4fJ4oQ2C','admin');
-- The hash above corresponds to password: Admin@123--
