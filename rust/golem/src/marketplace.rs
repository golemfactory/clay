pub fn order_providers(offers: &[f64]) -> Vec<usize> {
    let mut perm: Vec<usize> = (0..offers.len()).collect();
    perm.sort_by(|lhs, rhs| offers[*lhs].partial_cmp(&offers[*rhs]).unwrap());
    return perm
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn pick_provider_sanity() {
        assert_eq!(order_providers(&vec![2.0, 2.2, 1.7, 4.4]), vec![2, 0, 1, 3]);
    }
}
