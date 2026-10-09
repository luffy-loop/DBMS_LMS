// Lab Experiment 3: Flexible Data & The Aggregation Pipeline

// Step 1: Create / Use Database
use BookFlowDB

// Step 2: Create Collection
db.createCollection("book_metadata")

// Step 3: Insert Documents
db.book_metadata.insertMany([
  {
    book_id: 1,
    title: "Database Systems",
    published_year: 2021,
    format: "Digital PDF",
    file_size: "12 MB",
    reviews: [
      {
        member_id: 101,
        rating: 5,
        comments: "Excellent explanation of SQL and normalization."
      },
      {
        member_id: 102,
        rating: 4,
        comments: "Good examples with practical exercises."
      }
    ]
  },
  {
    book_id: 2,
    title: "Python Programming",
    published_year: 2023,
    format: "Digital EPUB",
    file_size: "18 MB",
    reviews: [
      {
        member_id: 103,
        rating: 5,
        comments: "Very beginner friendly."
      },
      {
        member_id: 104,
        rating: 5,
        comments: "Excellent coding examples."
      }
    ]
  },
  {
    book_id: 3,
    title: "Computer Networks",
    published_year: 2019,
    format: "Hardcover",
    dimensions: "8 x 10 inches",
    reviews: [
      {
        member_id: 105,
        rating: 3,
        comments: "Needs more practical examples."
      },
      {
        member_id: 106,
        rating: 4,
        comments: "Good networking concepts."
      }
    ]
  },
  {
    book_id: 4,
    title: "Cloud Computing",
    published_year: 2022,
    format: "Paperback",
    paper_weight: "250 GSM",
    reviews: [
      {
        member_id: 107,
        rating: 5,
        comments: "Excellent cloud architecture explanation."
      },
      {
        member_id: 108,
        rating: 4,
        comments: "Very useful for interviews."
      }
    ]
  }
])

// Step 4: View Documents
db.book_metadata.find().pretty()

// Step 5: Comparison Operator ($gt)
// Find books having at least one review rating greater than 4
db.book_metadata.find({
  "reviews.rating": { $gt: 4 }
})

// Step 6: Comparison Operator ($in)
// Find books available in Digital PDF or Hardcover format
db.book_metadata.find({
  format: {
    $in: ["Digital PDF", "Hardcover"]
  }
})

// Step 7: Regex Query
// Find books whose format contains the word "Digital"
db.book_metadata.find({
  format: {
    $regex: "Digital",
    $options: "i"
  }
})

// Step 8: Aggregation Pipeline
// Match books published after 2020
// Unwind reviews
// Group by title
// Calculate average rating

db.book_metadata.aggregate([
  {
    $match: {
      published_year: { $gt: 2020 }
    }
  },
  {
    $unwind: "$reviews"
  },
  {
    $group: {
      _id: "$title",
      Average_Rating: {
        $avg: "$reviews.rating"
      }
    }
  }
])

// Step 9: Create Text Index
db.book_metadata.createIndex({
  "reviews.comments": "text"
})

// Step 10: Search Using Text Index
db.book_metadata.find({
  $text: {
    $search: "Excellent"
  }
})

// Step 11: Verify Index Usage
db.book_metadata.find({
  $text: {
    $search: "Excellent"
  }
}).explain("executionStats")

// Step 12: List Indexes
db.book_metadata.getIndexes()