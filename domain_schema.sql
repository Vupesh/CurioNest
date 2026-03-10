-- CurioNest Dynamic Domain Configuration Schema

CREATE TABLE domains (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE boards (
    id SERIAL PRIMARY KEY,
    domain_id INT REFERENCES domains(id) ON DELETE CASCADE,
    name TEXT NOT NULL
);

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    board_id INT REFERENCES boards(id) ON DELETE CASCADE,
    name TEXT NOT NULL
);

CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    category_id INT REFERENCES categories(id) ON DELETE CASCADE,
    name TEXT NOT NULL
);

-- Initial Domain Data

INSERT INTO domains (name)
VALUES ('education');

INSERT INTO boards (domain_id, name)
VALUES
(1,'CBSE'),
(1,'ICSE');

INSERT INTO categories (board_id,name)
VALUES
(1,'Physics'),
(1,'Chemistry'),
(1,'Biology'),
(2,'Physics'),
(2,'Chemistry'),
(2,'Biology');