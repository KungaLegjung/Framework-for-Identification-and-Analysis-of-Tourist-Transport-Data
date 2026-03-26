CREATE DATABASE tourist_transport;
USE tourist_transport;

-- Admins table
CREATE TABLE admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE,
    password VARCHAR(255) NOT NULL
);

-- Users table
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255) NOT NULL
);

-- Places
CREATE TABLE places (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    location VARCHAR(100),
    description TEXT
);

-- Tours
CREATE TABLE tours (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    place_id INT,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(place_id) REFERENCES places(id)
);

-- Reviews
CREATE TABLE reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    review TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Chat
CREATE TABLE chat (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_type ENUM('admin','user'),
    sender_id INT,
    receiver_type ENUM('admin','user'),
    receiver_id INT,
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default Admin
INSERT INTO admins (username, password) VALUES ('admin', 'admin123');
