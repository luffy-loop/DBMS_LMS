-- =========================================
-- LAB 2: THE LIBRARIAN'S DASHBOARD
-- =========================================


-- =========================================
-- STEP 1: CREATE LOANS TABLE
-- =========================================

CREATE TABLE Loans (
    loan_id INT PRIMARY KEY,
    member_id INT,
    book_id INT,
    loan_date DATE,
    return_date DATE,

    CONSTRAINT fk_member
        FOREIGN KEY (member_id)
        REFERENCES Members(member_id),

    CONSTRAINT fk_book
        FOREIGN KEY (book_id)
        REFERENCES Books(book_id)
);


-- =========================================
-- STEP 2: INSERT SAMPLE LOAN DATA
-- =========================================

INSERT INTO Loans
VALUES
(1, 1, 101, '2026-07-01', NULL),
(2, 2, 102, '2026-07-02', NULL),
(3, 3, 103, '2026-07-03', NULL),
(4, 4, 111, '2026-07-04', NULL);


-- =========================================
-- TASK 1: CATALOG SEARCH - JOIN
-- =========================================

SELECT
    m.full_name,
    b.title
FROM Members m
JOIN Loans l
    ON m.member_id = l.member_id
JOIN Books b
    ON l.book_id = b.book_id;


-- =========================================
-- TASK 2: COLLECTION STATISTICS
-- =========================================

SELECT
    published_year,
    COUNT(book_id) AS total_books
FROM Books
GROUP BY published_year
ORDER BY published_year;


-- =========================================
-- TASK 3: CREATE DONATION HISTORY TABLE
-- =========================================

CREATE TABLE Donation_History (
    donation_id INT PRIMARY KEY,
    book_id INT,
    donor_name VARCHAR(100),
    donation_date DATE,

    CONSTRAINT fk_donation_book
        FOREIGN KEY (book_id)
        REFERENCES Books(book_id)
);


-- =========================================
-- DONATION TRANSACTION
-- =========================================

BEGIN;

INSERT INTO Books
VALUES
(
    104,
    'SQL Fundamentals',
    '9781239876540',
    2024
);

INSERT INTO Donation_History
VALUES
(
    1,
    104,
    'Anil Kumar',
    CURRENT_DATE
);

COMMIT;


-- =========================================
-- VERIFY DONATION
-- =========================================

SELECT * FROM Books;

SELECT * FROM Donation_History;


-- =========================================
-- ROLLBACK DEMONSTRATION
-- =========================================

BEGIN;

INSERT INTO Books
VALUES
(
    105,
    'Temporary Book',
    '9780000000000',
    2025
);

ROLLBACK;


-- Verify Temporary Book was NOT added
SELECT * FROM Books;


-- =========================================
-- TASK 4: SEARCH SPEED - INDEXING
-- =========================================

CREATE INDEX idx_books_isbn
ON Books(isbn);


-- =========================================
-- SEARCH BY ISBN
-- =========================================

SELECT *
FROM Books
WHERE isbn = '9781239876540';


-- =========================================
-- SEARCH BY TITLE
-- =========================================

SELECT *
FROM Books
WHERE title = 'SQL Fundamentals';