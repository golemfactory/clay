pub fn order_providers(offers: &[f64]) -> Vec<usize> {
    let mut perm = Vec::with_capacity(offers.len());
    for i in 0..offers.len() {
        perm.push(i);
    }
    perm.sort();
    return perm
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn pick_provider_sanity() {
        assert_eq!(order_providers(&vec![2.0, 2.2, 1.7, 4.4]), vec![0, 1, 2, 3]);
    }
}
