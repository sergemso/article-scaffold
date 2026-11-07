//! Fixture crate. fn fake() {}
use std::fmt;

/// Doc with braces { in a comment
pub struct Point {
    x: i32,
}

struct Unit;

pub enum Shape {
    Dot,
    Line { len: u32 },
}

pub trait Area {
    fn area(&self) -> f64;
    fn name(&self) -> &str {
        "shape"
    }
}

impl Point {
    pub fn new(x: i32) -> Self {
        let s = "fn not_a_fn() { }";
        Point { x }
    }

    pub async fn load(
        &self,
        n: u32,
    ) -> u32 {
        n
    }
}

impl<T: Clone> fmt::Display for Wrapper<T>
where
    T: fmt::Debug,
{
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{{}}")
    }
}

impl Area for Point {
    fn area(&self) -> f64 {
        0.0
    }
}

pub fn free<'a>(s: &'a str, c: char) -> &'a str {
    let _q = '{';
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn it_works() {
        assert_eq!(free("a", 'x'), "a");
    }

    #[tokio::test] async fn on_one_line() {}
}
