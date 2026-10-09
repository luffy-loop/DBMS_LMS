-- =========================================
-- LAB 1: BOOKFLOW DATABASE
-- =========================================

-- 1. CREATE BOOKS TABLE
CREATE TABLE Books (
    book_id INT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    isbn VARCHAR(20) UNIQUE,
    published_year INT CHECK (published_year < 2027)
);


-- 2. CREATE MEMBERS TABLE
CREATE TABLE Members (
    member_id INT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL
);


-- 3. INSERT 3 BOOKS
INSERT INTO Books
(book_id, title, isbn, published_year)
VALUES
(101, 'DBMS', '9780133970777', 2020),
(102, 'OS', '9781118063330', 2019),
(103, 'CN', '9780132126953', 2022);


-- 4. INSERT 3 MEMBERS
INSERT INTO Members
(member_id, full_name, email)
VALUES
(1, 'Rahul', 'rahul@gmail.com'),
(2, 'Priya', 'priya@gmail.com'),
(3, 'Anil', 'anil@gmail.com');


-- 5. VERIFY BOOKS
SELECT * FROM Books;


-- 6. VERIFY MEMBERS
SELECT * FROM Members;


-- =========================================
-- CONSTRAINT TESTING
-- =========================================

-- 7. DUPLICATE ISBN
-- This should give an ERROR
INSERT INTO Books
VALUES (104, 'SQL Basics', '9780133970777', 2023);


-- 8. DUPLICATE EMAIL
-- This should give an ERROR
INSERT INTO Members
VALUES (4, 'Ravi', 'rahul@gmail.com');


-- 9. NULL TITLE
-- This should give an ERROR
INSERT INTO Books
VALUES (105, NULL, '9781234567890', 2022);


-- 10. FUTURE YEAR
-- This should give an ERROR
INSERT INTO Books
VALUES (106, 'Future Book', '9789999999999', 2028);


-- =========================================
-- ADVANCED QUERIES
-- =========================================

-- 11. Display all books
SELECT * FROM Books;


-- 12. Display all members
SELECT * FROM Members;


-- 13. Books published after 2020
SELECT title, published_year
FROM Books
WHERE published_year > 2020;


-- 14. Sort books by title
SELECT *
FROM Books
ORDER BY title;


-- 15. Count books
SELECT COUNT(*) AS TotalBooks
FROM Books;


-- 16. Find oldest book
SELECT *
FROM Books
ORDER BY published_year
LIMIT 1;


-- 17. Search books containing "Computer"
SELECT *
FROM Books
WHERE title LIKE '%Computer%';


-- 18. Display member names alphabetically
SELECT full_name
FROM Members
ORDER BY full_name;


-- 19. Count registered members
SELECT COUNT(*) AS TotalMembers
FROM Members;


-- 20. Display distinct publication years
SELECT DISTINCT published_year
FROM Books;


-- =========================================
-- TRANSACTION
-- =========================================

-- 21. COMMIT example
BEGIN;

INSERT INTO Members
VALUES (4, 'Sneha', 'sneha@gmail.com');

COMMIT;


-- 22. ROLLBACK example
BEGIN;

INSERT INTO Members
VALUES (5, 'Test User', 'test@gmail.com');

ROLLBACK;


-- Verify members
SELECT * FROM Members;


-- =========================================
-- FUNCTION
-- =========================================

-- 23. Function to count books
CREATE OR REPLACE FUNCTION total_books()
RETURNS INTEGER
LANGUAGE plpgsql
AS
$$
DECLARE
    total INTEGER;
BEGIN
    SELECT COUNT(*) INTO total
    FROM Books;

    RETURN total;
END;
$$;


-- 24. Execute function
SELECT total_books();


-- =========================================
-- PROCEDURE
-- =========================================

-- 25. Create procedure
CREATE OR REPLACE PROCEDURE add_book(
    p_id INT,
    p_title VARCHAR,
    p_isbn VARCHAR,
    p_year INT
)
LANGUAGE plpgsql
AS
$$
BEGIN
    INSERT INTO Books
    VALUES (p_id, p_title, p_isbn, p_year);
END;
$$;


-- 26. Execute procedure
CALL add_book(
    111,
    'Java Fundamentals',
    '97812398782345',
    2022
);


-- 27. Verify new book
SELECT * FROM Books;